"""Análise técnica sobre barras históricas diárias do futuro subjacente."""

import logging
from dataclasses import dataclass
from typing import Optional

from ib_insync import Contract, IB

logger = logging.getLogger(__name__)


@dataclass
class TechIndicators:
    sma20:         Optional[float] = None
    sma50:         Optional[float] = None
    rsi_14:        Optional[float] = None
    bb_upper:      Optional[float] = None
    bb_lower:      Optional[float] = None
    bb_width:      Optional[float] = None   # (upper-lower)/sma20 — quanto menor, mais comprimido
    tendencia:     str = "LATERAL"           # ALTA | BAIXA | LATERAL
    sinal_tecnico: str = "NEUTRO"            # COMPRA | VENDA | BB_SQUEEZE | NEUTRO


# ── Funções puras de indicadores ──────────────────────────────────────────────

def _sma(closes: list[float], n: int) -> Optional[float]:
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 6)


def _rsi(closes: list[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_g  = sum(gains[:period]) / period
    avg_l  = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 2)


def _bollinger(closes: list[float], period: int = 20) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    sma    = sum(window) / period
    std    = (sum((x - sma) ** 2 for x in window) / period) ** 0.5
    upper  = sma + 2 * std
    lower  = sma - 2 * std
    width  = (upper - lower) / sma if sma else None
    return round(upper, 6), round(lower, 6), (round(width, 4) if width else None)


# ── Fetch + cálculo ──────────────────────────────────────────────────────────

def fetch_tech_indicators(ib: IB, symbol: str, exchange: str) -> TechIndicators:
    """Busca 65 dias de barras diárias e calcula SMA, RSI e Bollinger Bands."""
    try:
        fut     = Contract(symbol=symbol, secType="FUT", exchange=exchange, currency="USD")
        details = ib.reqContractDetails(fut)
        if not details:
            return TechIndicators()
        details.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)
        front = details[0].contract
        ib.qualifyContracts(front)

        bars = ib.reqHistoricalData(
            front,
            endDateTime="",
            durationStr="65 D",
            barSizeSetting="1 day",
            whatToShow="MIDPOINT",
            useRTH=True,
            formatDate=1,
        )
        if not bars or len(bars) < 15:
            logger.warning("[%s] Histórico insuficiente (%d barras).", symbol, len(bars) if bars else 0)
            return TechIndicators()

        closes = [b.close for b in bars]
        spot   = closes[-1]

        sma20          = _sma(closes, 20)
        sma50          = _sma(closes, 50)
        rsi            = _rsi(closes, 14)
        bb_up, bb_lo, bb_w = _bollinger(closes, 20)

        # Tendência
        if sma20 and sma50 and spot > sma20 and sma20 > sma50:
            tendencia = "ALTA"
        elif sma20 and sma50 and spot < sma20 and sma20 < sma50:
            tendencia = "BAIXA"
        else:
            tendencia = "LATERAL"

        # Sinal técnico
        if bb_w and bb_w < 0.008:
            sinal = "BB_SQUEEZE"    # bandas muito estreitas → expansão iminente
        elif rsi and rsi > 65 and sma20 and spot > sma20:
            sinal = "VENDA"         # sobrecomprado
        elif rsi and rsi < 35 and sma20 and spot < sma20:
            sinal = "COMPRA"        # sobrevendido
        else:
            sinal = "NEUTRO"

        logger.info("[%s] Técnico: sma20=%.5f rsi=%.1f bb_w=%.4f tend=%s sinal=%s",
                    symbol, sma20 or 0, rsi or 0, bb_w or 0, tendencia, sinal)

        return TechIndicators(
            sma20=sma20, sma50=sma50, rsi_14=rsi,
            bb_upper=bb_up, bb_lower=bb_lo, bb_width=bb_w,
            tendencia=tendencia, sinal_tecnico=sinal,
        )

    except Exception as e:
        logger.warning("[%s] Erro ao calcular indicadores técnicos: %s", symbol, e)
        return TechIndicators()
