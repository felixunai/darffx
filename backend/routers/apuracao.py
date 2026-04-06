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
from ..deps import get_db, get_current_user

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

    conteudo = await arquivo.read()

    # 1. Parse do PDF
    try:
        operacoes = parse_pdf_avatrade(BytesIO(conteudo))
    except Exception as e:
        raise HTTPException(422, f"Erro ao ler o PDF: {str(e)}")

    if not operacoes:
        raise HTTPException(422, "Nenhuma operação encontrada no arquivo.")

    # 2. Agrupa por mês/ano
    por_mes: dict = defaultdict(list)
    for op in operacoes:
        if op.tipo == "CLOSED":
            chave = (op.data.year, op.data.month)
            por_mes[chave].append(op)

    if not por_mes:
        raise HTTPException(422, "Nenhuma operação CLOSED encontrada.")

    # 3. Para cada mês, busca PTAX e calcula
    resultados = []
    for (ano, mes), ops in sorted(por_mes.items()):
        # verifica se já existe apuração para este mês
        existente = db.query(Apuracao).filter_by(
            user_id=usuario.id, mes=mes, ano=ano
        ).first()
        if existente:
            resultados.append(_apuracao_to_dict(existente))
            continue

        ptax = await buscar_ptax(mes, ano)
        if not ptax:
            ptax = 0.0  # salva com PTAX zerado para entrada manual

        resultado = calcular_ir_mensal(ops, ptax, mes, ano)

        # 4. Salva no banco
        apuracao = Apuracao(
            id=str(uuid.uuid4()),
            user_id=usuario.id,
            mes=mes, ano=ano,
            ganho_usd=resultado.ganho_usd,
            ptax=ptax,
            ganho_brl=resultado.ganho_brl,
            aliquota=resultado.aliquota,
            imposto_brl=resultado.imposto_brl,
            tem_day_trade=resultado.tem_day_trade,
        )
        db.add(apuracao)

        for op in ops:
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
        aliquota=apuracao.aliquota,
        imposto_brl=apuracao.imposto_brl,
        tem_day_trade=apuracao.tem_day_trade,
        operacoes_count=len(apuracao.operacoes),
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
    apuracao.imposto_brl = apuracao.ganho_brl * apuracao.aliquota if apuracao.ganho_brl > 0 else 0
    db.commit()
    return _apuracao_to_dict(apuracao)

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

def _apuracao_to_dict(a: Apuracao, incluir_operacoes=False) -> dict:
    d = {
        "id": a.id,
        "mes": a.mes,
        "ano": a.ano,
        "ganho_usd": a.ganho_usd,
        "ptax": a.ptax,
        "ganho_brl": a.ganho_brl,
        "aliquota": a.aliquota,
        "imposto_brl": a.imposto_brl,
        "tem_day_trade": a.tem_day_trade,
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
