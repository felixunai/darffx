from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import uuid
import secrets
import logging

logger = logging.getLogger(__name__)

from ..models.database import User
from ..deps import get_db, get_current_user
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _html_recuperacao(nome: str | None, link: str) -> str:
    saudacao = f"Olá{', ' + nome if nome else ''}!"
    return f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2 style="color:#00e5a0">DarfFX</h2>
      <p>{saudacao}</p>
      <p>Recebemos uma solicitação para redefinir sua senha.</p>
      <p style="margin:24px 0">
        <a href="{link}" style="background:#00e5a0;color:#000;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700">
          Redefinir senha →
        </a>
      </p>
      <p style="color:#999;font-size:13px">Este link expira em 2 horas. Se você não solicitou, ignore este e-mail.</p>
    </div>
    """


def _enviar_email_recuperacao(to_email: str, nome: str | None, link: str) -> None:
    """Tenta Resend primeiro; se não configurado/falhar, tenta Gmail SMTP."""
    html = _html_recuperacao(nome, link)
    assunto = "DarfFX — Recuperação de senha"

    # --- Resend ---
    if settings.RESEND_API_KEY:
        try:
            import resend
            resend.api_key = settings.RESEND_API_KEY
            result = resend.Emails.send({
                "from": settings.RESEND_FROM_EMAIL,
                "to": to_email,
                "subject": assunto,
                "html": html,
            })
            logger.info("E-mail enviado via Resend: %s → %s", to_email, result)
            return
        except Exception as e:
            logger.error("Resend falhou (%s) — tentando Gmail SMTP", e)

    # --- Brevo HTTP API ---
    if settings.BREVO_API_KEY and settings.BREVO_FROM_EMAIL:
        try:
            import httpx
            resp = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": settings.BREVO_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "sender": {"name": "DarfFX", "email": settings.BREVO_FROM_EMAIL},
                    "to": [{"email": to_email}],
                    "subject": assunto,
                    "htmlContent": html,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            logger.info("E-mail enviado via Brevo para %s (status %s)", to_email, resp.status_code)
            return
        except Exception as e:
            logger.error("Brevo falhou: %s", e)

    # --- Gmail SMTP ---
    if settings.SMTP_USER and settings.SMTP_PASSWORD:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            msg = MIMEMultipart("alternative")
            msg["Subject"] = assunto
            msg["From"] = f"DarfFX <{settings.SMTP_USER}>"
            msg["To"] = to_email
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.sendmail(settings.SMTP_USER, to_email, msg.as_string())
            logger.info("E-mail enviado via Gmail SMTP para %s", to_email)
            return
        except Exception as e:
            logger.error("Gmail SMTP falhou: %s", e)

    logger.warning("Nenhum provedor de e-mail configurado. E-mail não enviado para %s", to_email)

class RegisterIn(BaseModel):
    email: EmailStr
    senha: str
    nome: str | None = None

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

def criar_token(user_id: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": exp}, settings.SECRET_KEY, settings.ALGORITHM)

@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=data.email).first():
        raise HTTPException(400, "E-mail já cadastrado.")
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        nome=data.nome,
        hashed_password=pwd_ctx.hash(data.senha),
    )
    db.add(user)
    db.commit()
    return {"access_token": criar_token(user.id)}

@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=form.username).first()
    if not user or not pwd_ctx.verify(form.password, user.hashed_password):
        raise HTTPException(401, "E-mail ou senha incorretos.")
    return {"access_token": criar_token(user.id)}

class SolicitarResetIn(BaseModel):
    email: EmailStr

class ConfirmarResetIn(BaseModel):
    token: str
    nova_senha: str

@router.post("/recuperar-senha")
def solicitar_reset(data: SolicitarResetIn, db: Session = Depends(get_db)):
    """Envia e-mail de recuperação de senha via Resend."""
    user = db.query(User).filter_by(email=data.email).first()
    # Always return 200 to avoid email enumeration
    if not user:
        return {"ok": True, "msg": "Se o e-mail existir, você receberá as instruções."}

    from ..models.database import ResetToken
    # Invalidate old tokens
    db.query(ResetToken).filter_by(user_id=user.id, used=False).update({"used": True})

    token = secrets.token_urlsafe(32)
    rt = ResetToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(hours=2),
    )
    db.add(rt)
    db.commit()

    link = f"{settings.FRONTEND_URL}/nova-senha?token={token}"
    _enviar_email_recuperacao(user.email, user.nome, link)

    return {"ok": True, "msg": "Se o e-mail existir, você receberá as instruções."}


@router.post("/nova-senha")
def confirmar_reset(data: ConfirmarResetIn, db: Session = Depends(get_db)):
    from ..models.database import ResetToken
    rt = db.query(ResetToken).filter_by(token=data.token, used=False).first()
    if not rt or rt.expires_at < datetime.utcnow():
        raise HTTPException(400, "Link inválido ou expirado.")
    if len(data.nova_senha) < 6:
        raise HTTPException(400, "A senha deve ter pelo menos 6 caracteres.")

    user = db.query(User).filter_by(id=rt.user_id).first()
    user.hashed_password = pwd_ctx.hash(data.nova_senha)
    rt.used = True
    db.commit()
    return {"ok": True, "msg": "Senha redefinida com sucesso!"}


@router.get("/me")
def me(usuario: User = Depends(get_current_user)):
    from datetime import datetime
    expirado = (
        usuario.plano_expiracao is not None
        and usuario.plano_expiracao < datetime.utcnow()
        and usuario.plano == "pago"
    )
    return {
        "id":               usuario.id,
        "email":            usuario.email,
        "nome":             usuario.nome,
        "plano":            usuario.plano,
        "plano_expiracao":  usuario.plano_expiracao.isoformat() if usuario.plano_expiracao else None,
        "plano_expirado":   expirado,
        "is_admin":         usuario.email == "felixunai@gmail.com",
    }
