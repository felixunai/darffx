from sqlalchemy import Column, String, Float, Date, DateTime, Boolean, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime
import enum

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id            = Column(String, primary_key=True)
    email         = Column(String, unique=True, nullable=False)
    nome          = Column(String)
    hashed_password = Column(String, nullable=False)
    plano         = Column(String, default="free")  # free | pro
    stripe_customer_id = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    ativo         = Column(Boolean, default=True)

    apuracoes = relationship("Apuracao", back_populates="user", cascade="all, delete")

class Apuracao(Base):
    __tablename__ = "apuracoes"
    id            = Column(String, primary_key=True)
    user_id       = Column(String, ForeignKey("users.id"), nullable=False)
    mes           = Column(Integer, nullable=False)   # 1-12
    ano           = Column(Integer, nullable=False)
    ganho_usd     = Column(Float, default=0.0)
    ptax          = Column(Float, nullable=True)
    ganho_brl     = Column(Float, default=0.0)
    aliquota      = Column(Float, default=0.15)
    imposto_brl   = Column(Float, default=0.0)
    tem_day_trade = Column(Boolean, default=False)
    darf_pago     = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

    user       = relationship("User", back_populates="apuracoes")
    operacoes  = relationship("Operacao", back_populates="apuracao", cascade="all, delete")

class Operacao(Base):
    __tablename__ = "operacoes"
    id            = Column(String, primary_key=True)
    apuracao_id   = Column(String, ForeignKey("apuracoes.id"), nullable=False)
    adj_no        = Column(String)
    data          = Column(DateTime)
    tipo          = Column(String)   # OPENED / CLOSED / DEPOSIT
    descricao     = Column(String)
    valor_usd     = Column(Float)

    apuracao = relationship("Apuracao", back_populates="operacoes")
