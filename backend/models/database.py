from sqlalchemy import Column, String, Float, Date, DateTime, Boolean, Integer, ForeignKey, UniqueConstraint
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
    # planos: free | anual | admin
    plano            = Column(String, default="free")
    plano_expiracao  = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    ativo            = Column(Boolean, default=True)

    apuracoes         = relationship("Apuracao",      back_populates="user", cascade="all, delete")
    apuracoes_anuais  = relationship("ApuracaoAnual", back_populates="user", cascade="all, delete")
    pagamentos        = relationship("Pagamento",      back_populates="user", cascade="all, delete")


class ApuracaoAnual(Base):
    """
    Registro anual consolidado — Lei 14.754/2023.
    desbloqueado=False → teaser (free). True → relatório completo.
    """
    __tablename__ = "apuracoes_anuais"
    id                    = Column(String, primary_key=True)
    user_id               = Column(String, ForeignKey("users.id"), nullable=False)
    ano                   = Column(Integer, nullable=False)
    lucro_usd             = Column(Float, default=0.0)
    lucro_brl             = Column(Float, default=0.0)
    prejuizo_anterior_brl = Column(Float, default=0.0)
    base_tributavel_brl   = Column(Float, default=0.0)
    aliquota              = Column(Float, default=0.15)
    imposto_brl           = Column(Float, default=0.0)
    depositos_usd         = Column(Float, default=0.0)
    saques_usd            = Column(Float, default=0.0)
    vencimento_darf       = Column(Date, nullable=True)
    desbloqueado          = Column(Boolean, default=False)  # False = teaser; True = relatório pago
    darf_pago             = Column(Boolean, default=False)
    created_at            = Column(DateTime, default=datetime.utcnow)

    user  = relationship("User", back_populates="apuracoes_anuais")
    meses = relationship("Apuracao", back_populates="apuracao_anual",
                         foreign_keys="Apuracao.apuracao_anual_id",
                         cascade="all, delete-orphan")


class Apuracao(Base):
    """Breakdown mensal — detalhe dentro da apuração anual."""
    __tablename__ = "apuracoes"
    id               = Column(String, primary_key=True)
    user_id          = Column(String, ForeignKey("users.id"), nullable=False)
    apuracao_anual_id = Column(String, ForeignKey("apuracoes_anuais.id"), nullable=True)
    mes              = Column(Integer, nullable=False)
    ano              = Column(Integer, nullable=False)
    # Componentes da fórmula (Lei 14.754/2023)
    ganhos_usd       = Column(Float, default=0.0)   # Σ operações positivas
    perdas_usd       = Column(Float, default=0.0)   # Σ operações negativas (absoluto)
    custos_usd       = Column(Float, default=0.0)   # Taxas/corretagem
    ganho_usd        = Column(Float, default=0.0)   # ganhos − perdas − custos
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
    tipo          = Column(String)
    descricao     = Column(String)
    valor_usd     = Column(Float)
    ptax_data     = Column(Float, nullable=True)

    apuracao = relationship("Apuracao", back_populates="operacoes")


class PromoConfig(Base):
    """Configuração do plano promocional (linha única, id=1)."""
    __tablename__ = "promo_config"
    id             = Column(Integer, primary_key=True, default=1)
    ativo          = Column(Boolean, default=False)
    preco_centavos = Column(Integer, default=3990)   # R$39,90


class Pagamento(Base):
    """Registro de pagamentos Stripe."""
    __tablename__ = "pagamentos"
    id                = Column(String, primary_key=True)
    user_id           = Column(String, ForeignKey("users.id"), nullable=False)
    tipo              = Column(String)          # "relatorio" | "anual"
    ano               = Column(Integer, nullable=True)   # para tipo "relatorio"
    valor_brl         = Column(Float)
    stripe_session_id = Column(String, unique=True, nullable=True)
    status            = Column(String, default="pendente")  # pendente | pago | cancelado
    created_at        = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="pagamentos")


class ResetToken(Base):
    __tablename__ = "reset_tokens"
    token      = Column(String, primary_key=True)
    user_id    = Column(String, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used       = Column(Boolean, default=False)
    user = relationship("User")


class LembreteDarf(Base):
    """Rastreia lembretes de vencimento DARF já enviados — evita duplicatas."""
    __tablename__ = "lembretes_darf"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(String, ForeignKey("users.id"), nullable=False)
    ano        = Column(Integer, nullable=False)
    tipo       = Column(String, nullable=False)   # "30" | "7" | "1"
    enviado_em = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "ano", "tipo", name="uq_lembrete_darf"),)


class PtaxCache(Base):
    """Cache de cotações PTAX do Banco Central — evita chamadas repetidas à API BCB."""
    __tablename__ = "ptax_cache"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    mes           = Column(Integer, nullable=False)
    ano           = Column(Integer, nullable=False)
    ptax          = Column(Float, nullable=False)
    consultado_em = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("mes", "ano", name="uq_ptax_mes_ano"),)


class SinalOpcao(Base):
    """Sinal de operação estruturada em opções Forex (CME/IBKR). Gerado pelo agente local."""
    __tablename__ = "sinais_opcao"
    id                = Column(Integer, primary_key=True, autoincrement=True)
    par               = Column(String(20), nullable=False, index=True)   # "EUR/USD"
    symbol            = Column(String(10), nullable=False)               # "EUR"
    expiracao         = Column(Date, nullable=False)
    tipo_sinal        = Column(String(20), nullable=False)               # straddle|strangle|bull_spread|bear_spread
    strike_principal  = Column(Float)    # ATM strike
    strike_secundario = Column(Float)    # OTM strike (strangle/spread)
    premio_call       = Column(Float)    # mid-price call
    premio_put        = Column(Float)    # mid-price put
    custo_total       = Column(Float)    # prêmio total da estrutura
    delta_call        = Column(Float)
    delta_put         = Column(Float)
    gamma             = Column(Float)
    theta_call        = Column(Float)
    vega_call         = Column(Float)
    iv_call           = Column(Float)
    iv_put            = Column(Float)
    iv_media          = Column(Float)    # (iv_call + iv_put) / 2
    iv_skew           = Column(Float)    # iv_call - iv_put (skew direcional)
    spot_price        = Column(Float)
    volume_call       = Column(Integer)
    volume_put        = Column(Integer)
    oi_call           = Column(Integer)  # open interest call
    oi_put            = Column(Integer)  # open interest put
    iv_rank_30d       = Column(Float)    # 0-100, min-max sobre últimos 30 dias
    score             = Column(Float)    # qualidade do sinal 0-100
    recomendacao      = Column(String(15))  # BUY|SELL|NEUTRAL|BULL_SPREAD|BEAR_SPREAD
    # Análise técnica
    rsi_14            = Column(Float)    # RSI 14 períodos do futuro subjacente
    sma20             = Column(Float)    # Média móvel 20 dias
    sma50             = Column(Float)    # Média móvel 50 dias
    bb_width          = Column(Float)    # Largura das Bandas de Bollinger (compressão)
    tendencia         = Column(String(10))  # ALTA | BAIXA | LATERAL
    pc_ratio          = Column(Float)    # Razão put/call de volume
    # Explicação humana
    motivo            = Column(String(700))  # texto explicando o sinal
    strikes_recomendados = Column(String(250))  # strikes sugeridos formatados
    # Métricas de risco para strangle vendido
    dte               = Column(Integer, default=0)   # dias até vencimento
    prob_profit       = Column(Float)                 # POP % (0-100)
    expected_move     = Column(Float)                 # mov. 1σ esperado até vencimento
    criado_em         = Column(DateTime, default=datetime.utcnow, index=True)
