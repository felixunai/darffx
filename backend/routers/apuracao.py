"""
Router: /apuracao
- POST /apuracao/upload  — recebe PDF, processa, salva e retorna resultado
- GET  /apuracao/        — lista apurações do usuário
- GET  /apuracao/{id}    — detalhe de uma apuração
- GET  /apuracao/{id}/pdf — download do relatório PDF
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from collections import defaultdict
import uuid
from io import BytesIO

from ..services.parser_avatrade import parse_pdf_avatrade
from ..services.calculo_ir import buscar_ptax, calcular_ir_mensal
from ..services.gerador_pdf import gerar_relatorio_pdf
from ..models.database import Apuracao, Operacao, User
from ..deps import get_db, get_current_user, ADMIN_EMAIL
from datetime import datetime

router = APIRouter(prefix="/apuracao", tags=["apuracao"])

@router.post("/upload")
async def upload_extrato(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    """
    Recebe o PDF da AvaTrade, faz o parse, busca PTAX e calcula IR de cada mês.
    Retorna lista de apurações mensais.
    """
    if not arquivo.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Envie um arquivo PDF.")

    # Verificação de plano
    _verificar_plano(usuario, db)

    conteudo = await arquivo.read()

    # 1. Parse do PDF
    try:
        operacoes = parse_pdf_avatrade(BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(422, f"Erro ao ler o PDF: {str(e)}")

    if not operacoes:
        raise HTTPException(422, "Nenhuma operação encontrada no arquivo.")

    # 2. Agrupa por mês/ano (inclui todos os tipos)
    por_mes: dict = defaultdict(list)
    for op in operacoes:
        chave = (op.data.year, op.data.month)
        por_mes[chave].append(op)

    tem_closed = any(
        op.tipo == "CLOSED" for ops in por_mes.values() for op in ops
    )
    if not por_mes or not tem_closed:
        raise HTTPException(422, "Nenhuma operação CLOSED encontrada.")

    # 3. Carry Forward: lê perdas acumuladas de apurações já existentes (anteriores)
    apuracoes_existentes = (
        db.query(Apuracao)
        .filter_by(user_id=usuario.id)
        .order_by(Apuracao.ano, Apuracao.mes)
        .all()
    )
    acumulado_perdas_brl = 0.0
    for ap in apuracoes_existentes:
        if ap.ganho_brl < 0:
            acumulado_perdas_brl += abs(ap.ganho_brl)
        elif ap.ganho_brl > 0:
            acumulado_perdas_brl = max(0.0, acumulado_perdas_brl - ap.ganho_brl)

    # 4. Para cada mês (ordem cronológica), busca PTAX e calcula
    resultados = []
    for (ano, mes), ops in sorted(por_mes.items()):
        existente = db.query(Apuracao).filter_by(
            user_id=usuario.id, mes=mes, ano=ano
        ).first()
        if existente:
            resultados.append(_apuracao_to_dict(existente))
            # atualiza carry forward com base no resultado existente
            if existente.ganho_brl < 0:
                acumulado_perdas_brl += abs(existente.ganho_brl)
            elif existente.ganho_brl > 0:
                acumulado_perdas_brl = max(0.0, acumulado_perdas_brl - existente.ganho_brl)
            continue

        ptax = await buscar_ptax(mes, ano)
        if not ptax:
            ptax = 0.0

        resultado = calcular_ir_mensal(ops, ptax, mes, ano, carry_fwd_brl=acumulado_perdas_brl)

        # Calcula depósitos e saques do mês
        depositos_usd = sum(
            op.valor_usd for op in ops
            if op.tipo == "DEPOSIT" and op.valor_usd > 0
        )
        saques_usd = sum(
            abs(op.valor_usd) for op in ops
            if op.tipo in ("DEPOSIT", "WITHDRAWAL") and op.valor_usd < 0
        )

        # Atualiza carry forward para próximo mês
        if resultado.ganho_brl < 0:
            acumulado_perdas_brl += abs(resultado.ganho_brl)
        elif resultado.ganho_brl > 0:
            acumulado_perdas_brl = max(0.0, acumulado_perdas_brl - resultado.ganho_brl)

        # 5. Salva no banco
        apuracao = Apuracao(
            id=str(uuid.uuid4()),
            user_id=usuario.id,
            mes=mes, ano=ano,
            ganho_usd=resultado.ganho_usd,
            ptax=ptax,
            ganho_brl=resultado.ganho_brl,
            carry_fwd_brl=resultado.carry_fwd_brl,
            base_ir_brl=resultado.base_tributavel_brl,
            aliquota=resultado.aliquota,
            imposto_brl=resultado.imposto_brl,
            tem_day_trade=resultado.tem_day_trade,
            depositos_usd=depositos_usd,
            saques_usd=saques_usd,
            vencimento_darf=resultado.vencimento_darf,
        )
        db.add(apuracao)

        for op in ops:
            if op.tipo not in ("CLOSED", "OPENED", "DEPOSIT"):
                continue
            db.add(Operacao(
                id=str(uuid.uuid4()),
                apuracao_id=apuracao.id,
                adj_no=op.adj_no,
                data=op.data,
                tipo=op.tipo,
                descricao=op.descricao,
                valor_usd=op.valor_usd,
            ))

        db.commit()
        db.refresh(apuracao)
        resultados.append(_apuracao_to_dict(apuracao))

    return {"apuracoes": resultados, "total": len(resultados)}

@router.get("/")
def listar_apuracoes(
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    apuracoes = (
        db.query(Apuracao)
        .filter_by(user_id=usuario.id)
        .order_by(Apuracao.ano.desc(), Apuracao.mes.desc())
        .all()
    )
    return [_apuracao_to_dict(a) for a in apuracoes]

@router.get("/{apuracao_id}")
def detalhe_apuracao(
    apuracao_id: str,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    apuracao = db.query(Apuracao).filter_by(
        id=apuracao_id, user_id=usuario.id
    ).first()
    if not apuracao:
        raise HTTPException(404, "Apuração não encontrada.")
    return _apuracao_to_dict(apuracao, incluir_operacoes=True)

@router.get("/{apuracao_id}/pdf")
def download_pdf(
    apuracao_id: str,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    apuracao = db.query(Apuracao).filter_by(
        id=apuracao_id, user_id=usuario.id
    ).first()
    if not apuracao:
        raise HTTPException(404, "Apuração não encontrada.")

    from ..services.calculo_ir import ResultadoMensal
    resultado = ResultadoMensal(
        mes=apuracao.mes, ano=apuracao.ano,
        ganho_usd=apuracao.ganho_usd,
        ptax=apuracao.ptax,
        ganho_brl=apuracao.ganho_brl,
        carry_fwd_brl=apuracao.carry_fwd_brl or 0.0,
        base_tributavel_brl=apuracao.base_ir_brl or apuracao.ganho_brl,
        aliquota=apuracao.aliquota,
        imposto_brl=apuracao.imposto_brl,
        tem_day_trade=apuracao.tem_day_trade,
        operacoes_count=len(apuracao.operacoes),
        vencimento_darf=apuracao.vencimento_darf,
    )

    pdf_bytes = gerar_relatorio_pdf(resultado, usuario.nome or usuario.email)
    nome_arquivo = f"darffx_{apuracao.ano}_{apuracao.mes:02d}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )

@router.patch("/{apuracao_id}/ptax")
def atualizar_ptax(
    apuracao_id: str,
    ptax: float,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    """Permite o usuário informar o PTAX manualmente caso a API do BCB falhe."""
    apuracao = db.query(Apuracao).filter_by(
        id=apuracao_id, user_id=usuario.id
    ).first()
    if not apuracao:
        raise HTTPException(404, "Apuração não encontrada.")

    apuracao.ptax = ptax
    apuracao.ganho_brl = apuracao.ganho_usd * ptax
    carry = apuracao.carry_fwd_brl or 0.0
    base = max(0.0, apuracao.ganho_brl - carry) if apuracao.ganho_brl > 0 else 0.0
    apuracao.base_ir_brl = base
    apuracao.imposto_brl = base * apuracao.aliquota if base > 0 else 0.0
    db.commit()
    return _apuracao_to_dict(apuracao)

@router.delete("/{apuracao_id}")
def deletar_apuracao(
    apuracao_id: str,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    """Remove uma apuração e suas operações para permitir reprocessamento."""
    apuracao = db.query(Apuracao).filter_by(
        id=apuracao_id, user_id=usuario.id
    ).first()
    if not apuracao:
        raise HTTPException(404, "Apuração não encontrada.")
    db.query(Operacao).filter_by(apuracao_id=apuracao_id).delete()
    db.delete(apuracao)
    db.commit()
    return {"ok": True}

@router.patch("/{apuracao_id}/pago")
def marcar_pago(
    apuracao_id: str,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    apuracao = db.query(Apuracao).filter_by(
        id=apuracao_id, user_id=usuario.id
    ).first()
    if not apuracao:
        raise HTTPException(404, "Apuração não encontrada.")
    apuracao.darf_pago = True
    db.commit()
    return {"ok": True}

def _verificar_plano(usuario, db: Session):
    """Verifica se o usuário pode fazer upload conforme seu plano."""
    # Admin e planos pagos não expirados: liberado
    if usuario.email == ADMIN_EMAIL or usuario.plano == "admin":
        return

    # Planos pagos: verifica expiração
    if usuario.plano in ("mensal", "anual"):
        if usuario.plano_expiracao and usuario.plano_expiracao < datetime.utcnow():
            raise HTTPException(
                402,
                "Seu plano expirou. Renove em felixunai@gmail.com ou acesse o painel para reativar."
            )
        return

    # Plano free: máximo 1 mês de apuração
    count = db.query(Apuracao).filter_by(user_id=usuario.id).count()
    if count >= 1:
        raise HTTPException(
            402,
            "Plano gratuito permite apenas 1 mês de apuração. "
            "Faça upgrade para o plano Mensal (R$ 19,90) ou Anual (R$ 199,00)."
        )


def _apuracao_to_dict(a: Apuracao, incluir_operacoes=False) -> dict:
    d = {
        "id": a.id,
        "mes": a.mes,
        "ano": a.ano,
        "ganho_usd": a.ganho_usd,
        "ptax": a.ptax,
        "ganho_brl": a.ganho_brl,
        "carry_fwd_brl": a.carry_fwd_brl or 0.0,
        "base_ir_brl": a.base_ir_brl or a.ganho_brl,
        "aliquota": a.aliquota,
        "imposto_brl": a.imposto_brl,
        "tem_day_trade": a.tem_day_trade,
        "depositos_usd": a.depositos_usd or 0.0,
        "saques_usd": a.saques_usd or 0.0,
        "vencimento_darf": a.vencimento_darf.isoformat() if a.vencimento_darf else None,
        "darf_pago": a.darf_pago,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
    if incluir_operacoes:
        d["operacoes"] = [
            {
                "adj_no": op.adj_no,
                "data": op.data.isoformat() if op.data else None,
                "tipo": op.tipo,
                "descricao": op.descricao,
                "valor_usd": op.valor_usd,
            }
            for op in a.operacoes
        ]
    return d
