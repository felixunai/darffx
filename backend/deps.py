from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from jose import jwt, JWTError

from .config import settings
from .models.database import Base, User, PromoConfig, ResetToken

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,          # conexões permanentes no pool
    max_overflow=20,       # conexões extras sob pico (total máx: 30)
    pool_timeout=30,       # segundos esperando conexão livre antes de erro
    pool_recycle=1800,     # recria conexões a cada 30 min (evita conexão morta)
    pool_pre_ping=True,    # testa conexão antes de usar (detecta quedas do banco)
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

ADMIN_EMAIL = "felixunai@gmail.com"

_MIGRATIONS = [
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS carry_fwd_brl FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS base_ir_brl FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS depositos_usd FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS saques_usd FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS vencimento_darf DATE",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS apuracao_anual_id VARCHAR REFERENCES apuracoes_anuais(id) ON DELETE SET NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS plano_expiracao TIMESTAMP",
    "ALTER TABLE operacoes ADD COLUMN IF NOT EXISTS ptax_data FLOAT",
    "ALTER TABLE apuracoes_anuais ADD COLUMN IF NOT EXISTS desbloqueado BOOLEAN DEFAULT FALSE",
    "CREATE TABLE IF NOT EXISTS reset_tokens (token VARCHAR PRIMARY KEY, user_id VARCHAR REFERENCES users(id) ON DELETE CASCADE, expires_at TIMESTAMP NOT NULL, used BOOLEAN DEFAULT FALSE)",
    # Fórmula explícita Lei 14.754/2023: ganhos − perdas − custos
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS ganhos_usd FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS perdas_usd FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS custos_usd FLOAT DEFAULT 0",
]

def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for sql in _MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()
    # Garante que existe uma linha de config de promo
    db = SessionLocal()
    try:
        if not db.query(PromoConfig).filter_by(id=1).first():
            db.add(PromoConfig(id=1, ativo=False, preco_centavos=3990))
            db.commit()
    finally:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Token inválido.")
    except JWTError:
        raise HTTPException(401, "Token inválido ou expirado.")

    user = db.query(User).filter_by(id=user_id, ativo=True).first()
    if not user:
        raise HTTPException(401, "Usuário não encontrado.")
    return user

def get_admin_user(usuario: User = Depends(get_current_user)) -> User:
    if usuario.email != ADMIN_EMAIL:
        raise HTTPException(403, "Acesso restrito ao administrador.")
    return usuario
