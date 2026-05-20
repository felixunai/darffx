"""Busca a cadeia de opções FOP do próximo vencimento para um par CME."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

from ib_insync import Contract, FuturesOption, IB

from .config import MIN_LIQUID_STRIKES

logger = logging.getLogger(__name__)


@dataclass
class OptionLeg:
    strike: float
    right: str          # "C" ou "P"
    expiry: str         # "YYYYMMDD"
    bid: float
    ask: float
    mid: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    iv: Optional[float] = None
    volume: int = 0
    open_interest: int = 0


@dataclass
class OptionsChain:
    symbol: str
    par: str
    expiry: str
    spot: float
    dte: int = 0
    invert_spot: bool = False
    calls: list[OptionLeg] = field(default_factory=list)
    puts: list[OptionLeg] = field(default_factory=list)


def _nearest_expiry(expirations: list[str]) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    futuros = sorted(e for e in expirations if e >= today)
    if not futuros:
        raise ValueError("Nenhum vencimento futuro encontrado.")
    return futuros[0]


def _calc_dte(expiry: str) -> int:
    exp_date = datetime.strptime(expiry, "%Y%m%d").date()
    return max(0, (exp_date - date.today()).days)


def _find_future_with_options(ib: IB, symbol: str, exchange: str):
    """
    Itera pelos futuros disponíveis (mais próximos primeiro) e retorna
    (contrato_qualificado, lista_de_chains) do primeiro que tiver opções ativas.
    """
    fut = Contract(symbol=symbol, secType="FUT", exchange=exchange, currency="USD")
    details = ib.reqContractDetails(fut)
    if not details:
        return None, []

    details.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)

    for d in details[:6]:
        ctr = d.contract
        qualified = ib.qualifyContracts(ctr)
        if not qualified:
            continue
        ctr = qualified[0]

        chains = ib.reqSecDefOptParams(symbol, exchange, "FUT", ctr.conId)
        if chains:
            logger.debug("[%s] Opções encontradas no contrato %s (conId=%s)",
                         symbol, ctr.lastTradeDateOrContractMonth, ctr.conId)
            return ctr, chains

    return None, []


def _get_spot(ib: IB, front: Contract) -> float:
    """Mid-price do futuro. Usa dados atrasados (gratuitos)."""
    ib.reqMarketDataType(3)
    ticker = ib.reqMktData(front, "", False, False)
    ib.sleep(3)
    bid  = ticker.bid  if ticker.bid  and ticker.bid  > 0 else None
    ask  = ticker.ask  if ticker.ask  and ticker.ask  > 0 else None
    last = ticker.last if ticker.last and ticker.last > 0 else None
    ib.cancelMktData(front)
    if bid and ask:
        return (bid + ask) / 2
    return float(last or 0.0)


def fetch_chain(ib: IB, symbol: str, par: str, exchange: str = "CME", invert_spot: bool = False) -> Optional[OptionsChain]:
    """
    Busca a cadeia FOP do próximo vencimento com opções ativas.

    Otimização: qualifica todos os contratos em batch (asyncio.gather interno
    do ib_insync) e faz um único sleep para todos os market data, reduzindo o
    tempo de ~90s/par para ~8s/par.
    """
    # 1. Encontrar o futuro que tem opções ativas
    front, chains = _find_future_with_options(ib, symbol, exchange)
    if not front or not chains:
        logger.warning("[%s] Nenhuma cadeia de opções encontrada.", symbol)
        return None

    chain = next((c for c in chains if c.exchange == exchange), chains[0])
    opt_exchange = chain.exchange or exchange

    try:
        expiry = _nearest_expiry(list(chain.expirations))
    except ValueError as e:
        logger.warning("[%s] %s", symbol, e)
        return None

    strikes = sorted(chain.strikes)

    # 2. Spot price
    try:
        spot_raw = _get_spot(ib, front)
        if spot_raw <= 0:
            raise ValueError("Spot inválido.")
        spot = (1.0 / spot_raw) if invert_spot else spot_raw
    except Exception as e:
        logger.warning("[%s] Erro ao buscar spot: %s", symbol, e)
        return None

    # 3. Os 30 strikes mais próximos do ATM
    atm_strikes = sorted(strikes, key=lambda s: abs(s - spot_raw))[:30]

    # 4. Monta todos os contratos e qualifica em batch
    #    ib_insync usa asyncio.gather internamente → todos os reqContractDetails
    #    vão em paralelo, levando ~0.5s no total em vez de 30s sequencialmente.
    all_opts: list[tuple[float, str, FuturesOption]] = []
    for strike in sorted(atm_strikes):
        for right in ("C", "P"):
            opt = FuturesOption(
                symbol=symbol,
                lastTradeDateOrContractMonth=expiry,
                strike=strike,
                right=right,
                exchange=opt_exchange,
            )
            all_opts.append((strike, right, opt))

    raw_list = [o for _, _, o in all_opts]
    try:
        ib.qualifyContracts(*raw_list)
        # qualifyContracts preenche conId in-place nos objetos de raw_list
    except Exception as e:
        logger.warning("[%s] Erro ao qualificar contratos em batch: %s", symbol, e)
        return None

    # 5. Dispara reqMktData para todos os contratos válidos de uma vez
    ib.reqMarketDataType(3)
    pending: list[tuple[float, str, FuturesOption, object]] = []
    for strike, right, opt in all_opts:
        if not getattr(opt, "conId", 0):
            continue
        ticker = ib.reqMktData(opt, "106", False, False)
        pending.append((strike, right, opt, ticker))

    # 6. Dorme uma única vez — todos os ~60 tickers populam juntos
    ib.sleep(3.5)

    # 7. Lê resultados e cancela todas as subscriptions
    calls_raw: list[OptionLeg] = []
    puts_raw:  list[OptionLeg] = []
    for strike, right, opt, ticker in pending:
        ib.cancelMktData(opt)

        bid = ticker.bid if ticker.bid and ticker.bid > 0 else 0.0
        ask = ticker.ask if ticker.ask and ticker.ask > 0 else 0.0
        mid = (bid + ask) / 2

        if bid <= 0 and ask <= 0:
            continue

        greeks = ticker.modelGreeks
        oi = getattr(ticker, "openInterest", None) or getattr(ticker, "optOpenInterest", None) or 0
        display_strike = (1.0 / strike) if invert_spot and strike > 0 else strike

        leg = OptionLeg(
            strike=display_strike,
            right=right,
            expiry=expiry,
            bid=bid,
            ask=ask,
            mid=mid,
            delta=greeks.delta    if greeks else None,
            gamma=greeks.gamma    if greeks else None,
            theta=greeks.theta    if greeks else None,
            vega=greeks.vega      if greeks else None,
            iv=greeks.impliedVol  if greeks else ticker.impliedVolatility,
            volume=int(getattr(ticker, "volume", 0) or 0),
            open_interest=int(oi),
        )
        bucket = calls_raw if right == "C" else puts_raw
        bucket.append(leg)

    liquid_calls = [c for c in calls_raw if c.bid > 0 or c.ask > 0]
    liquid_puts  = [p for p in puts_raw  if p.bid > 0 or p.ask > 0]

    # Para pares invertidos (USD/JPY, USD/CAD) a semântica call/put da CME é oposta:
    #   CME call CAD/USD = lucra se CAD sobe  = USD/CAD cai  = "put" na visão do usuário
    #   CME put  CAD/USD = lucra se CAD cai   = USD/CAD sobe = "call" na visão do usuário
    # Solução: trocar os buckets e negar os deltas para que o signal_engine opere
    # corretamente no espaço de preços do usuário.
    if invert_spot:
        for leg in liquid_calls + liquid_puts:
            if leg.delta is not None:
                leg.delta = -leg.delta
        liquid_calls, liquid_puts = liquid_puts, liquid_calls

    if len(liquid_calls) < MIN_LIQUID_STRIKES or len(liquid_puts) < MIN_LIQUID_STRIKES:
        logger.warning("[%s] Liquidez insuficiente (%d calls, %d puts). Par ignorado.",
                       symbol, len(liquid_calls), len(liquid_puts))
        return None

    dte = _calc_dte(expiry)
    logger.info("[%s] Cadeia OK: expiry=%s DTE=%d spot=%.5f calls=%d puts=%d",
                symbol, expiry, dte, spot, len(liquid_calls), len(liquid_puts))

    return OptionsChain(
        symbol=symbol,
        par=par,
        expiry=expiry,
        spot=spot,
        dte=dte,
        invert_spot=invert_spot,
        calls=sorted(liquid_calls, key=lambda l: l.strike),
        puts=sorted(liquid_puts,   key=lambda l: l.strike),
    )
