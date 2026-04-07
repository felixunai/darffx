from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import uuid

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

@router.get("/me")
def me(usuario: User = Depends(get_current_user)):
    from datetime import datetime
    expirado = (
        usuario.plano_expiracao is not None
        and usuario.plano_expiracao < datetime.utcnow()
        and usuario.plano not in ("free", "admin")
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
