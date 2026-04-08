"""
Router: /pagamento

Plano único: R$69,90 — acesso completo até 31/12 do ano vigente.

POST /pagamento/checkout        — cria sessão Stripe
POST /pagamento/webhook         — recebe eventos Stripe
GET  /pagamento/status/{ano}    — verifica se relatório está desbloqueado
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from ..config import settings
from ..models.database import ApuracaoAnual, Pagamento, User, PromoConfig
from ..deps import get_db, get_current_user

router = APIRouter(prefix="/pagamento", tags=["pagamento"])

PRECO_NORMAL = settings.PRECO_ACESSO_CENTAVOS   # R$69,90


def _get_preco_ativo(db: Session) -> tuple[int, bool]:
    """Retorna (preco_centavos, is_promo). Usa promo se estiver ativa."""
    promo = db.query(PromoConfig).filter_by(id=1).first()
    if promo and promo.ativo:
        return promo.preco_centavos, True
    return PRECO_NORMAL, False


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


def _expiracao_ano_vigente() -> datetime:
    """Retorna 31/12 do ano corrente às 23:59:59 UTC."""
    ano = datetime.utcnow().year
    return datetime(ano, 12, 31, 23, 59, 59)


# ── CONFIG PÚBLICA ────────────────────────────────────────────────────────────

@router.get("/promo")
def get_promo_publica(db: Session = Depends(get_db)):
    """Retorna preço ativo (normal ou promo) para exibição na página de upgrade."""
    preco, is_promo = _get_preco_ativo(db)
    return {
        "promo_ativa": is_promo,
        "preco_centavos": preco,
        "preco_brl": f"R$ {preco / 100:.2f}".replace(".", ","),
        "preco_normal_brl": f"R$ {PRECO_NORMAL / 100:.2f}".replace(".", ","),
    }


# ── CHECKOUT ──────────────────────────────────────────────────────────────────

@router.post("/checkout")
async def checkout(
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user),
):
    """Cria sessão de pagamento Stripe — Acesso Completo R$69,90 (expira 31/12)."""
    # Já tem plano pago e não expirado
    if usuario.plano == "pago" and usuario.plano_expiracao and usuario.plano_expiracao > datetime.utcnow():
        raise HTTPException(400, "Você já possui acesso ativo até 31/12.")

    ano_atual = datetime.utcnow().year
    preco, is_promo = _get_preco_ativo(db)

    stripe = _get_stripe()
    nome_produto = f"DarfFX — Acesso Completo {ano_atual}"
    if is_promo:
        nome_produto += " 🏷 Oferta Especial"

    product_data = {
        "name": nome_produto,
        "description": (
            f"✓ Cálculo automático Lei 14.754/2023  ·  "
            f"✓ PTAX automático (Banco Central)  ·  "
            f"✓ Exportação para declaração IRPF  ·  "
            f"✓ Meses ilimitados  ·  "
            f"✓ Válido até 31/12/{ano_atual}"
        ),
    }
    if settings.STRIPE_PRODUCT_IMAGE_URL:
        product_data["images"] = [settings.STRIPE_PRODUCT_IMAGE_URL]

    session = stripe.checkout.Session.create(
        payment_method_types=["card", "pix"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": product_data,
                "unit_amount": preco,
            },
            "quantity": 1,
        }],
        mode="payment",
        customer_email=usuario.email,
        custom_text={
            "submit": {
                "message": "Pagamento único e seguro via Stripe. Acesso liberado imediatamente após confirmação.",
            },
            "after_submit": {
                "message": "Você receberá um email de confirmação assim que o pagamento for processado.",
            },
        },
        success_url=f"{settings.FRONTEND_URL}/apuracao/anual/{ano_atual}?desbloqueado=1",
        cancel_url=f"{settings.FRONTEND_URL}/upgrade?cancelado=1",
        metadata={
            "user_id": usuario.id,
            "tipo": "acesso",
        },
    )

    pagamento = Pagamento(
        id=str(uuid.uuid4()),
        user_id=usuario.id,
        tipo="acesso",
        ano=ano_atual,
        valor_brl=preco / 100,
        stripe_session_id=session.id,
        status="pendente",
    )
    db.add(pagamento)
    db.commit()

    return {"checkout_url": session.url, "session_id": session.id}


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
        session_id = session["id"]

        # Marca pagamento como pago
        pag = db.query(Pagamento).filter_by(stripe_session_id=session_id).first()
        if pag:
            pag.status = "pago"

        if user_id:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                # Seta plano pago com expiração 31/12 do ano vigente
                user.plano = "pago"
                user.plano_expiracao = _expiracao_ano_vigente()
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
    is_pago = (
        usuario.plano in ("pago", "admin")
        and (usuario.plano_expiracao is None or usuario.plano_expiracao > datetime.utcnow())
    )
    desbloqueado = bool(anual and anual.desbloqueado) or is_admin or is_pago
    return {
        "ano": ano,
        "desbloqueado": desbloqueado,
        "plano": usuario.plano,
    }
