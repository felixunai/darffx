"""
Router: /pagamento

Gerencia checkout Stripe e desbloqueio de relatórios.

POST /pagamento/checkout/relatorio/{ano}  — cria sessão Stripe (R$69)
POST /pagamento/checkout/anual            — cria sessão upsell Stripe (R$49)
POST /pagamento/webhook                   — recebe eventos Stripe
GET  /pagamento/status/{ano}             — verifica se relatório está desbloqueado
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from ..config import settings
from ..models.database import ApuracaoAnual, Pagamento, User
from ..deps import get_db, get_current_user

router = APIRouter(prefix="/pagamento", tags=["pagamento"])

PRECO_RELATORIO = settings.PRECO_RELATORIO_CENTAVOS   # R$69,00
PRECO_ANUAL     = settings.PRECO_ANUAL_CENTAVOS       # R$49,00


def _get_stripe():
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            503,
            "Pagamento temporariamente indisponível. "
            "Entre em contato: felixunai@gmail.com"
        )
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        raise HTTPException(503, "Stripe não instalado no servidor.")


# ── CHECKOUT RELATÓRIO COMPLETO ───────────────────────────────────────────────

@router.post("/checkout/relatorio/{ano}")
async def checkout_relatorio(
    ano: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    """Cria sessão de pagamento Stripe para desbloquear relatório de um ano (R$69)."""
    # Verifica se já está desbloqueado
    anual = db.query(ApuracaoAnual).filter_by(user_id=usuario.id, ano=ano).first()
    if not anual:
        raise HTTPException(404, "Apuração anual não encontrada.")
    if anual.desbloqueado:
        raise HTTPException(400, "Este relatório já está desbloqueado.")

    # Verifica se já tem pagamento pendente
    pag_existente = db.query(Pagamento).filter_by(
        user_id=usuario.id, tipo="relatorio", ano=ano, status="pendente"
    ).first()

    stripe = _get_stripe()
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {
                    "name": f"DarfFX — Relatório IR Forex {ano}",
                    "description": f"Cálculo oficial 15% · PTAX automático · Relatório para IRPF {ano}",
                },
                "unit_amount": PRECO_RELATORIO,
            },
            "quantity": 1,
        }],
        mode="payment",
        customer_email=usuario.email,
        success_url=f"{settings.FRONTEND_URL}/apuracao/anual/{ano}?desbloqueado=1",
        cancel_url=f"{settings.FRONTEND_URL}/upgrade?ano={ano}&cancelado=1",
        metadata={
            "user_id": usuario.id,
            "ano": str(ano),
            "tipo": "relatorio",
        },
    )

    pagamento = Pagamento(
        id=str(uuid.uuid4()),
        user_id=usuario.id,
        tipo="relatorio",
        ano=ano,
        valor_brl=PRECO_RELATORIO / 100,
        stripe_session_id=session.id,
        status="pendente",
    )
    db.add(pagamento)
    db.commit()

    return {"checkout_url": session.url, "session_id": session.id}


# ── CHECKOUT ACESSO ANUAL (UPSELL) ────────────────────────────────────────────

@router.post("/checkout/anual")
async def checkout_anual(
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    """Cria sessão Stripe para Acesso Anual ilimitado (R$49 — upsell pós-relatório)."""
    if usuario.plano == "anual" and usuario.plano_expiracao and usuario.plano_expiracao > datetime.utcnow():
        raise HTTPException(400, "Você já possui Acesso Anual ativo.")

    stripe = _get_stripe()
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {
                    "name": "DarfFX — Acesso Anual",
                    "description": "Reprocessamento ilimitado · Histórico completo · 12 meses",
                },
                "unit_amount": PRECO_ANUAL,
            },
            "quantity": 1,
        }],
        mode="payment",
        customer_email=usuario.email,
        success_url=f"{settings.FRONTEND_URL}/?upgrade=anual",
        cancel_url=f"{settings.FRONTEND_URL}/?cancelado=1",
        metadata={
            "user_id": usuario.id,
            "tipo": "anual",
        },
    )

    pagamento = Pagamento(
        id=str(uuid.uuid4()),
        user_id=usuario.id,
        tipo="anual",
        ano=None,
        valor_brl=PRECO_ANUAL / 100,
        stripe_session_id=session.id,
        status="pendente",
    )
    db.add(pagamento)
    db.commit()

    return {"checkout_url": session.url}


# ── WEBHOOK STRIPE ────────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    stripe = _get_stripe()
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(400, "Assinatura Stripe inválida.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        meta    = session.get("metadata", {})
        user_id = meta.get("user_id")
        tipo    = meta.get("tipo")
        session_id = session["id"]

        # Marca pagamento como pago
        pag = db.query(Pagamento).filter_by(stripe_session_id=session_id).first()
        if pag:
            pag.status = "pago"

        if tipo == "relatorio":
            ano = int(meta.get("ano", 0))
            if ano and user_id:
                anual = db.query(ApuracaoAnual).filter_by(user_id=user_id, ano=ano).first()
                if anual:
                    anual.desbloqueado = True

        elif tipo == "anual":
            if user_id:
                user = db.query(User).filter_by(id=user_id).first()  # noqa: F821
                if user:
                    user.plano = "anual"
                    user.plano_expiracao = datetime.utcnow() + timedelta(days=365)
                    # Desbloqueia todos os relatórios do usuário
                    db.query(ApuracaoAnual).filter_by(user_id=user_id).update(
                        {"desbloqueado": True}
                    )

        db.commit()

    return {"ok": True}


# ── STATUS ────────────────────────────────────────────────────────────────────

@router.get("/status/{ano}")
def status_relatorio(
    ano: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    anual = db.query(ApuracaoAnual).filter_by(user_id=usuario.id, ano=ano).first()
    is_admin = usuario.email == "felixunai@gmail.com"
    is_anual = (
        usuario.plano == "anual"
        and (usuario.plano_expiracao is None or usuario.plano_expiracao > datetime.utcnow())
    )
    desbloqueado = bool(anual and anual.desbloqueado) or is_admin or is_anual
    return {
        "ano": ano,
        "desbloqueado": desbloqueado,
        "plano": usuario.plano,
    }
