"""
Backfill de 30 dias de IV histórica via IBKR — popula o IV Rank imediatamente.

Uso:
    python -m signals_agent.main --backfill
"""

import logging
import math
from datetime import datetime, timedelta

from ib_insync import IB

from .chain_fetcher import _find_future_with_options, _nearest_expiry
from .config import PAIRS
from .pusher import push_signals
from .signal_engine import Signal
from .synthetic import CORR_EUR_JPY

logger = logging.getLogger(__name__)

BACKFILL_DAYS = 30


def _date_to_iso(raw: str) -> str:
    """Normaliza 'YYYYMMDD' ou '2024-05-01 00:00:00' para 'YYYY-MM-DDTHH:MM:SS'."""
    raw = raw.strip()
    if " " in raw:
        date_part = raw.split(" ")[0]
        return f"{date_part}T12:00:00"
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}T12:00:00"


def backfill_pair(ib: IB, symbol: str, par: str, exchange: str,
                  invert_spot: bool = False) -> list[Signal]:
    """
    Busca 30 dias de IV histórica (ATM) + spot do futuro via IBKR e
    monta registros skeleton para popular o IV Rank 30d no banco.
    """
    front, chains = _find_future_with_options(ib, symbol, exchange)
    if not front or not chains:
        logger.warning("[%s] Nenhum contrato encontrado para backfill.", symbol)
        return []

    chain = next((c for c in chains if c.exchange == exchange), chains[0])
    try:
        expiry = _nearest_expiry(list(chain.expirations))
    except ValueError:
        return []

    expiry_iso = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:]}"

    # Busca IV histórica (ATM impliedVol do futuro subjacente)
    try:
        iv_bars = ib.reqHistoricalData(
            front,
            endDateTime="",
            durationStr=f"{BACKFILL_DAYS} D",
            barSizeSetting="1 day",
            whatToShow="OPTION_IMPLIED_VOLATILITY",
            useRTH=True,
            formatDate=1,
        )
    except Exception as e:
        logger.error("[%s] Erro ao buscar IV histórica: %s", symbol, e)
        return []

    if not iv_bars:
        logger.warning("[%s] Nenhuma barra de IV histórica retornada.", symbol)
        return []

    # Busca spot histórico para o mesmo período
    try:
        spot_bars = ib.reqHistoricalData(
            front,
            endDateTime="",
            durationStr=f"{BACKFILL_DAYS} D",
            barSizeSetting="1 day",
            whatToShow="MIDPOINT",
            useRTH=True,
            formatDate=1,
        )
        spot_map = {b.date: b.close for b in spot_bars} if spot_bars else {}
    except Exception:
        spot_map = {}

    signals: list[Signal] = []
    for bar in iv_bars:
        iv = bar.close
        if not iv or iv <= 0:
            continue

        # IBKR retorna IV como decimal (ex: 0.065) ou percentual (ex: 6.5)?
        # Se > 1.0, está em percentual — converter
        if iv > 1.0:
            iv = iv / 100.0

        spot_raw = spot_map.get(bar.date, 0.0) or 0.0
        spot = (1.0 / spot_raw) if (invert_spot and spot_raw > 0) else spot_raw

        criado_em = _date_to_iso(str(bar.date))

        for tipo in ("straddle", "strangle", "bull_spread", "bear_spread"):
            sig = Signal(
                par=par,
                symbol=symbol,
                expiracao=expiry_iso,
                tipo_sinal=tipo,
                strike_principal=None,
                strike_secundario=None,
                premio_call=None,
                premio_put=None,
                custo_total=None,
                delta_call=None,
                delta_put=None,
                gamma=None,
                theta_call=None,
                vega_call=None,
                iv_call=iv,
                iv_put=iv,
                iv_media=round(iv, 6),
                iv_skew=None,
                spot_price=spot,
                volume_call=None,
                volume_put=None,
                oi_call=None,
                oi_put=None,
                score=50.0,
                recomendacao="NEUTRAL",
                motivo="[backfill histórico]",
                strikes_recomendados="",
            )
            # Adiciona data retroativa como atributo extra — o pusher usa asdict()
            sig._criado_em_override = criado_em  # type: ignore[attr-defined]
            signals.append(sig)

    logger.info("[%s] Backfill: %d barras × 4 tipos = %d registros gerados.",
                symbol, len(iv_bars), len(signals))
    return signals


def backfill_eurjpy_synthetic(ib: IB) -> list[Signal]:
    """
    Backfill sintético EUR/JPY: combina IV histórica de EUR/USD e USD/JPY
    usando a mesma fórmula de variância de portfólio do synthetic.py.

    Gera iv_media diferenciada por tipo para garantir IV Rank consistente:
      straddle / bull_spread / bear_spread → iv_syn        (ATM)
      strangle                             → iv_syn × 0.97 (OTM, igual ao agente)
    """
    IV_STRANGLE_FACTOR = 0.97

    eur_front, eur_chains = _find_future_with_options(ib, "EUR", "CME")
    jpy_front, jpy_chains = _find_future_with_options(ib, "JPY", "CME")

    if not eur_front or not jpy_front:
        logger.warning("[EUR/JPY backfill] Contrato EUR ou JPY não encontrado.")
        return []

    eur_chain = next((c for c in eur_chains if c.exchange == "CME"), eur_chains[0]) if eur_chains else None
    try:
        expiry = _nearest_expiry(list(eur_chain.expirations))
        expiry_iso = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:]}"
    except (ValueError, AttributeError):
        expiry_iso = "2025-12-31"

    def _fetch(front, what):
        try:
            return ib.reqHistoricalData(
                front, endDateTime="", durationStr=f"{BACKFILL_DAYS} D",
                barSizeSetting="1 day", whatToShow=what,
                useRTH=True, formatDate=1,
            )
        except Exception as e:
            logger.error("[EUR/JPY backfill] Erro %s %s: %s", front.symbol, what, e)
            return []

    eur_iv_bars   = _fetch(eur_front, "OPTION_IMPLIED_VOLATILITY")
    jpy_iv_bars   = _fetch(jpy_front, "OPTION_IMPLIED_VOLATILITY")
    eur_spot_bars = _fetch(eur_front, "MIDPOINT")
    jpy_spot_bars = _fetch(jpy_front, "MIDPOINT")

    def _as_iv_map(bars):
        m = {}
        for b in bars:
            v = b.close
            if not v or v <= 0:
                continue
            if v > 1.0:
                v = v / 100.0
            m[str(b.date)] = v
        return m

    eur_iv_map   = _as_iv_map(eur_iv_bars)
    jpy_iv_map   = _as_iv_map(jpy_iv_bars)
    eur_spot_map = {str(b.date): b.close for b in eur_spot_bars} if eur_spot_bars else {}
    jpy_spot_map = {str(b.date): b.close for b in jpy_spot_bars} if jpy_spot_bars else {}

    common_dates = sorted(set(eur_iv_map) & set(jpy_iv_map))
    if not common_dates:
        logger.warning("[EUR/JPY backfill] Nenhuma data comum EUR×JPY.")
        return []

    signals: list[Signal] = []
    for date_str in common_dates:
        iv_eur = eur_iv_map[date_str]
        iv_jpy = jpy_iv_map[date_str]

        variance = iv_eur**2 + iv_jpy**2 + 2 * CORR_EUR_JPY * iv_eur * iv_jpy
        iv_syn = math.sqrt(max(variance, 1e-8))

        spot_eur_raw = eur_spot_map.get(date_str, 0.0) or 0.0
        spot_jpy_raw = jpy_spot_map.get(date_str, 0.0) or 0.0
        spot = round(spot_eur_raw / spot_jpy_raw, 3) if spot_jpy_raw > 0 else 0.0

        criado_em = _date_to_iso(date_str)

        iv_by_tipo = {
            "straddle":    iv_syn,
            "strangle":    iv_syn * IV_STRANGLE_FACTOR,
            "bull_spread": iv_syn,
            "bear_spread": iv_syn,
        }

        for tipo, iv_media in iv_by_tipo.items():
            sig = Signal(
                par="EUR/JPY",
                symbol="EURJPY",
                expiracao=expiry_iso,
                tipo_sinal=tipo,
                strike_principal=None,
                strike_secundario=None,
                premio_call=None,
                premio_put=None,
                custo_total=None,
                delta_call=None,
                delta_put=None,
                gamma=None,
                theta_call=None,
                vega_call=None,
                iv_call=iv_syn,
                iv_put=iv_syn,
                iv_media=round(iv_media, 6),
                iv_skew=None,
                spot_price=spot,
                volume_call=None,
                volume_put=None,
                oi_call=None,
                oi_put=None,
                score=50.0,
                recomendacao="NEUTRAL",
                motivo="[backfill sintético EUR/JPY]",
                strikes_recomendados="",
            )
            sig._criado_em_override = criado_em  # type: ignore[attr-defined]
            signals.append(sig)

    logger.info("[EUR/JPY backfill] %d datas × 4 tipos = %d registros gerados.",
                len(common_dates), len(signals))
    return signals


def run_backfill(dry_run: bool = False) -> None:
    from .connector import get_ib, disconnect

    ib = get_ib()
    total = 0
    for pair in PAIRS:
        signals = backfill_pair(
            ib,
            symbol=pair["symbol"],
            par=pair["par"],
            exchange=pair.get("exchange", "CME"),
            invert_spot=pair.get("invert_spot", False),
        )
        if signals:
            ok = push_signals(signals, dry_run=dry_run, backfill=True)
            if ok:
                total += len(signals)

    # EUR/JPY não tem FOP na CME — backfill sintético via composição EUR×JPY
    eurjpy_signals = backfill_eurjpy_synthetic(ib)
    if eurjpy_signals:
        ok = push_signals(eurjpy_signals, dry_run=dry_run, backfill=True)
        if ok:
            total += len(eurjpy_signals)

    disconnect()
    logger.info("Backfill concluído: %d registros enviados.", total)
