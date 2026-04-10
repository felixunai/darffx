"""
Router: /cron

Endpoints chamados por jobs externos (Railway Cron, GitHub Actions, etc.).
Protegidos pelo header X-Cron-Secret que deve bater com CRON_SECRET no .env.

POST /cron/lembretes-darf  — envia e-mails de vencimento DARF (30d, 7d, 1d)
"""
from fastapi import APIRouter, Depends, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from ..deps import get_db
from ..config import settings
from ..models.database import ApuracaoAnual, User, LembreteDarf

router = APIRouter(prefix="/cron", tags=["cron"])

MESES_NOME = [
    "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro",
]


def _checar_secret(x_cron_secret: str = Header(None, alias="x-cron-secret")):
    if not settings.CRON_SECRET or x_cron_secret != settings.CRON_SECRET:
        raise HTTPException(403, "Acesso negado.")


@router.post("/lembretes-darf", dependencies=[Depends(_checar_secret)])
async def enviar_lembretes_darf(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Verifica todos os usuários com DARF pendente e envia lembretes a 30, 7 e 1 dia
    do vencimento. Idempotente — nunca envia o mesmo tipo de lembrete duas vezes.
    """
    from ..routers.auth import _enviar_email

    hoje = datetime.utcnow().date()

    anuais = (
        db.query(ApuracaoAnual)
        .filter(
            ApuracaoAnual.darf_pago == False,
            ApuracaoAnual.desbloqueado == True,
            ApuracaoAnual.imposto_brl > 0,
            ApuracaoAnual.vencimento_darf != None,
        )
        .all()
    )

    enviados = 0
    for anual in anuais:
        venc = anual.vencimento_darf
        dias = (venc - hoje).days

        tipo = None
        if   dias == 30: tipo = "30"
        elif dias == 7:  tipo = "7"
        elif dias == 1:  tipo = "1"

        if not tipo:
            continue

        # Idempotência — pula se já foi enviado
        ja_enviado = db.query(LembreteDarf).filter_by(
            user_id=anual.user_id, ano=anual.ano, tipo=tipo
        ).first()
        if ja_enviado:
            continue

        user = db.query(User).filter_by(id=anual.user_id, ativo=True).first()
        if not user:
            continue

        db.add(LembreteDarf(user_id=anual.user_id, ano=anual.ano, tipo=tipo))

        html  = _html_lembrete(user.nome or user.email, venc, anual.imposto_brl, dias, anual.ano)
        assunto = f"⏰ DARF vence em {dias} {'dia' if dias == 1 else 'dias'} — DarfFX"
        background_tasks.add_task(_enviar_email, user.email, assunto, html)
        enviados += 1

    db.commit()
    return {"ok": True, "enviados": enviados, "verificados": len(anuais)}


def _html_lembrete(nome: str, vencimento, imposto_brl: float, dias: int, ano: int) -> str:
    venc_fmt = vencimento.strftime("%d/%m/%Y") if vencimento else "—"
    imposto_fmt = f"R$ {imposto_brl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    cor_urgencia = "#FF4D6D" if dias <= 7 else "#FFB347"
    msg_urgencia = (
        "Falta apenas 1 dia!" if dias == 1
        else f"Faltam {dias} dias."
    )

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lembrete DARF — DarfFX</title></head>
<body style="margin:0;padding:0;background:#0a0e17;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e17;padding:40px 0;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#111827;border-radius:16px;border:1px solid rgba(255,255,255,0.07);overflow:hidden;max-width:560px;width:100%;">

      <!-- Header -->
      <tr><td style="padding:32px 40px 24px;border-bottom:1px solid rgba(255,255,255,0.07);">
        <p style="margin:0;font-size:22px;font-weight:800;color:#e8edf5;letter-spacing:-0.5px;">
          Darf<span style="color:#00e5a0;">FX</span>
        </p>
      </td></tr>

      <!-- Countdown badge -->
      <tr><td style="padding:32px 40px 0;text-align:center;">
        <div style="display:inline-block;background:rgba({('255,77,109' if dias <= 7 else '255,179,71')},0.12);
          border:1px solid {cor_urgencia};border-radius:12px;padding:20px 32px;">
          <p style="margin:0;font-size:48px;font-weight:800;color:{cor_urgencia};line-height:1;">{dias}</p>
          <p style="margin:4px 0 0;font-size:13px;color:#6b7a99;text-transform:uppercase;letter-spacing:1px;">
            {'dia restante' if dias == 1 else 'dias restantes'}
          </p>
        </div>
      </td></tr>

      <!-- Body -->
      <tr><td style="padding:28px 40px;">
        <p style="margin:0 0 8px;font-size:15px;color:#6b7a99;">Olá, {nome}!</p>
        <h2 style="margin:0 0 16px;font-size:20px;font-weight:700;color:#e8edf5;line-height:1.3;">
          Seu DARF de {ano} vence em {venc_fmt}. {msg_urgencia}
        </h2>
        <p style="margin:0 0 24px;font-size:14px;color:#6b7a99;line-height:1.7;">
          Não perca o prazo para recolher o imposto sobre seus ganhos no Forex.
          Atrasos geram multa de 0,33% ao dia (máx. 20%) + juros Selic.
        </p>

        <!-- Imposto box -->
        <div style="background:#1a2235;border-radius:10px;padding:20px 24px;margin-bottom:24px;border:1px solid rgba(255,255,255,0.07);">
          <p style="margin:0 0 4px;font-size:11px;color:#6b7a99;text-transform:uppercase;letter-spacing:0.5px;">Imposto a recolher ({ano})</p>
          <p style="margin:0;font-size:26px;font-weight:800;color:{cor_urgencia};">{imposto_fmt}</p>
          <p style="margin:6px 0 0;font-size:12px;color:#6b7a99;">Lei 14.754/2023 · Alíquota 15% · Aplicações financeiras no exterior</p>
        </div>

        <a href="{settings.FRONTEND_URL}/dashboard" style="display:block;text-align:center;
          background:#00e5a0;color:#0a0e17;font-weight:700;font-size:15px;
          padding:14px 24px;border-radius:10px;text-decoration:none;">
          Acessar meu relatório →
        </a>
      </td></tr>

      <!-- Footer -->
      <tr><td style="padding:20px 40px;border-top:1px solid rgba(255,255,255,0.07);text-align:center;">
        <p style="margin:0;font-size:11px;color:#6b7a99;">
          DarfFX · IR Forex · Lei 14.754/2023<br>
          Para não receber mais estes lembretes, marque o DARF como pago no sistema.
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body></html>
"""
