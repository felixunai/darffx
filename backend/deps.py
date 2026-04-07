from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from jose import jwt, JWTError

from .config import settings
from .models.database import Base, User

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Novas colunas adicionadas ao modelo — migração incremental para tabelas existentes
_MIGRATIONS = [
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS carry_fwd_brl FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS base_ir_brl FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS depositos_usd FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS saques_usd FLOAT DEFAULT 0",
    "ALTER TABLE apuracoes ADD COLUMN IF NOT EXISTS vencimento_darf DATE",
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
