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

    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY não configurado — e-mail de recuperação não enviado para %s", user.email)
    else:
        try:
            import resend
            resend.api_key = settings.RESEND_API_KEY
            link = f"{settings.FRONTEND_URL}/nova-senha?token={token}"
            result = resend.Emails.send({
                "from": settings.RESEND_FROM_EMAIL,
                "to": user.email,
                "subject": "DarfFX — Recuperação de senha",
                "html": f"""
                <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
                  <h2 style="color:#00e5a0">DarfFX</h2>
                  <p>Olá{', ' + user.nome if user.nome else ''}!</p>
                  <p>Recebemos uma solicitação para redefinir sua senha.</p>
                  <p style="margin:24px 0">
                    <a href="{link}" style="background:#00e5a0;color:#000;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700">
                      Redefinir senha →
                    </a>
                  </p>
                  <p style="color:#999;font-size:13px">Este link expira em 2 horas. Se você não solicitou, ignore este e-mail.</p>
                </div>
                """,
            })
            logger.info("E-mail de recuperação enviado: %s → id=%s", user.email, result)
        except Exception as e:
            logger.error("Falha ao enviar e-mail de recuperação para %s: %s", user.email, e)

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
