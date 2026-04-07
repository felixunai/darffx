from sqlalchemy import Column, String, Float, Date, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id               = Column(String, primary_key=True)
    email            = Column(String, unique=True, nullable=False)
    nome             = Column(String)
    hashed_password  = Column(String, nullable=False)
    plano            = Column(String, default="free")
    plano_expiracao  = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    ativo            = Column(Boolean, default=True)

    apuracoes         = relationship("Apuracao",      back_populates="user", cascade="all, delete")
    apuracoes_anuais  = relationship("ApuracaoAnual", back_populates="user", cascade="all, delete")


class ApuracaoAnual(Base):
    """
    Registro anual de IR — Lei 14.754/2023.
    Alíquota fixa de 15% sobre lucro líquido anual (sem isenção, sem DARF mensal).
    Vencimento: último dia útil de maio do ano seguinte (prazo IRPF).
    """
    __tablename__ = "apuracoes_anuais"
    id                    = Column(String, primary_key=True)
    user_id               = Column(String, ForeignKey("users.id"), nullable=False)
    ano                   = Column(Integer, nullable=False)
    # P&L de trading (CLOSED + OPENED)
    lucro_usd             = Column(Float, default=0.0)
    lucro_brl             = Column(Float, default=0.0)
    # Compensação de perdas
    prejuizo_anterior_brl = Column(Float, default=0.0)  # carry forward de anos anteriores
    base_tributavel_brl   = Column(Float, default=0.0)
    # Imposto
    aliquota              = Column(Float, default=0.15)
    imposto_brl           = Column(Float, default=0.0)
    # Fluxos de caixa (para declaração)
    depositos_usd         = Column(Float, default=0.0)
    saques_usd            = Column(Float, default=0.0)
    # Prazo e status
    vencimento_darf       = Column(Date, nullable=True)
    darf_pago             = Column(Boolean, default=False)
    created_at            = Column(DateTime, default=datetime.utcnow)

    user  = relationship("User", back_populates="apuracoes_anuais")
    meses = relationship("Apuracao", back_populates="apuracao_anual",
                         foreign_keys="Apuracao.apuracao_anual_id",
                         cascade="all, delete-orphan")


class Apuracao(Base):
    """
    Breakdown mensal — serve como registro de detalhe dentro da apuração anual.
    Não gera DARF próprio; é agregado no ApuracaoAnual.
    """
    __tablename__ = "apuracoes"
    id               = Column(String, primary_key=True)
    user_id          = Column(String, ForeignKey("users.id"), nullable=False)
    apuracao_anual_id = Column(String, ForeignKey("apuracoes_anuais.id"), nullable=True)
    mes              = Column(Integer, nullable=False)
    ano              = Column(Integer, nullable=False)
    ganho_usd        = Column(Float, default=0.0)
    ptax             = Column(Float, nullable=True)
    ganho_brl        = Column(Float, default=0.0)
    carry_fwd_brl    = Column(Float, default=0.0)
    base_ir_brl      = Column(Float, default=0.0)
    aliquota         = Column(Float, default=0.15)
    imposto_brl      = Column(Float, default=0.0)
    tem_day_trade    = Column(Boolean, default=False)
    depositos_usd    = Column(Float, default=0.0)
    saques_usd       = Column(Float, default=0.0)
    vencimento_darf  = Column(Date, nullable=True)
    darf_pago        = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=datetime.utcnow)

    user           = relationship("User", back_populates="apuracoes")
    apuracao_anual = relationship("ApuracaoAnual", back_populates="meses",
                                  foreign_keys=[apuracao_anual_id])
    operacoes      = relationship("Operacao", back_populates="apuracao", cascade="all, delete")


class Operacao(Base):
    __tablename__ = "operacoes"
    id            = Column(String, primary_key=True)
    apuracao_id   = Column(String, ForeignKey("apuracoes.id"), nullable=False)
    adj_no        = Column(String)
    data          = Column(DateTime)
    tipo          = Column(String)   # OPENED / CLOSED / DEPOSIT / WITHDRAWAL
    descricao     = Column(String)
    valor_usd     = Column(Float)
    ptax_data     = Column(Float, nullable=True)   # PTAX do dia da operação

    apuracao = relationship("Apuracao", back_populates="operacoes")
