"""
Síntese de EUR/JPY a partir das cadeias EUR/USD e USD/JPY.

Metodologia:
  spot_EURJPY = spot_EURUSD × spot_USDJPY
  iv_EURJPY   = √(iv_eur² + iv_jpy² + 2ρ·iv_eur·iv_jpy)   ρ ≈ −0.35 (correlação histórica típica)
  strikes     = ATM e ±16-delta estimados por Black-Scholes aproximado
  tendência   = composição EUR/USD × USD/JPY (lógica de cross rate)
"""

import logging
import math
from typing import Optional

from .chain_fetcher import OptionLeg, OptionsChain
from .tech_analysis import TechIndicators

logger = logging.getLogger(__name__)

# Correlação histórica entre retornos EUR/USD e USD/JPY (tipicamente negativa)
CORR_EUR_JPY: float = -0.35

# z-score para delta 16: norminv(1 - 0.16) ≈ norminv(0.84) ≈ 0.994
Z_DELTA16: float = 0.994

# Mapeamento de tendência composta para pares cruzados
# EUR/JPY = EUR/USD × USD/JPY → tendência é composição das duas direções
_TEND_COMPOSITE = {
    ("ALTA",    "ALTA"):    "ALTA",
    ("ALTA",    "BAIXA"):   "LATERAL",
    ("ALTA",    "LATERAL"): "ALTA",
    ("BAIXA",   "ALTA"):    "LATERAL",
    ("BAIXA",   "BAIXA"):   "BAIXA",
    ("BAIXA",   "LATERAL"): "BAIXA",
    ("LATERAL", "ALTA"):    "ALTA",
    ("LATERAL", "BAIXA"):   "BAIXA",
    ("LATERAL", "LATERAL"): "LATERAL",
}


def _atm_iv(chain: OptionsChain) -> Optional[float]:
    """Média das IVs das 3 opções mais próximas do ATM em cada lado."""
    spot = chain.spot
    legs = sorted(chain.calls + chain.puts, key=lambda l: abs(l.strike - spot))[:6]
    ivs = [l.iv for l in legs if l.iv and l.iv > 0]
    return sum(ivs) / len(ivs) if ivs else None


def synthesize_eurjpy_chain(eur_chain: OptionsChain, jpy_chain: OptionsChain) -> Optional[OptionsChain]:
    """
    Cria uma OptionsChain sintética para EUR/JPY.

    eur_chain.spot deve ser EUR/USD (ex: 1.0850).
    jpy_chain.spot deve ser USD/JPY já invertido (ex: 158.56).
    Retorna None se não houver IV suficiente nas cadeias componentes.
    """
    spot = round(eur_chain.spot * jpy_chain.spot, 3)

    iv_eur = _atm_iv(eur_chain)
    iv_jpy = _atm_iv(jpy_chain)
    if not iv_eur or not iv_jpy:
        logger.warning("[EUR/JPY] IV insuficiente para síntese (eur=%s, jpy=%s)", iv_eur, iv_jpy)
        return None

    # IV sintética via fórmula de variância de portfólio com correlação
    variance = iv_eur**2 + iv_jpy**2 + 2 * CORR_EUR_JPY * iv_eur * iv_jpy
    iv_syn = math.sqrt(max(variance, 1e-8))
    logger.info("[EUR/JPY] spot=%.3f iv_syn=%.4f (eur=%.4f jpy=%.4f ρ=%.2f)",
                spot, iv_syn, iv_eur, iv_jpy, CORR_EUR_JPY)

    # DTE: usa o vencimento mais próximo entre os dois pares
    dte = min(eur_chain.dte, jpy_chain.dte) if min(eur_chain.dte, jpy_chain.dte) > 0 else max(eur_chain.dte, jpy_chain.dte)
    expiry = eur_chain.expiry if eur_chain.dte <= jpy_chain.dte else jpy_chain.expiry

    sqrt_t = math.sqrt(max(dte / 365.0, 0.001))

    # Prêmio ATM (Black-Scholes ATM simplificado): C ≈ S·σ·√T·(1/√2π) ≈ S·σ·√T·0.3989
    prem_atm = round(spot * iv_syn * sqrt_t * 0.3989, 2)

    # Strikes OTM para delta 16: S·exp(±z·σ·√T)
    call_otm_strike = round(spot * math.exp( Z_DELTA16 * iv_syn * sqrt_t), 2)
    put_otm_strike  = round(spot * math.exp(-Z_DELTA16 * iv_syn * sqrt_t), 2)
    prem_otm = round(prem_atm * 0.18, 2)  # aprox. 18% do ATM para opção de ~16 delta

    def _leg(strike, right, delta, iv, prem):
        return OptionLeg(
            strike=strike, right=right, expiry=expiry,
            bid=round(prem * 0.97, 2), ask=round(prem * 1.03, 2), mid=prem,
            delta=delta, gamma=None, theta=None, vega=None,
            iv=iv, volume=0, open_interest=0,
        )

    calls = sorted([
        _leg(spot,            "C",  0.50,  iv_syn,        prem_atm),
        _leg(call_otm_strike, "C",  0.16,  iv_syn * 0.97, prem_otm),
    ], key=lambda l: l.strike)

    puts = sorted([
        _leg(put_otm_strike,  "P", -0.16, iv_syn * 0.97, prem_otm),
        _leg(spot,            "P", -0.50, iv_syn,        prem_atm),
    ], key=lambda l: l.strike)

    return OptionsChain(
        symbol="EURJPY",
        par="EUR/JPY",
        expiry=expiry,
        spot=spot,
        dte=dte,
        invert_spot=False,  # EUR/JPY já está em convenção natural (JPY por EUR, ex: 172)
        calls=calls,
        puts=puts,
    )


def blend_tech(eur_tech: TechIndicators, jpy_tech: TechIndicators) -> TechIndicators:
    """
    Combina indicadores técnicos de EUR/USD e USD/JPY para gerar tech do EUR/JPY.
    Tendência usa lógica de cross rate: EUR/JPY = EUR/USD × USD/JPY.
    RSI e BB são médias ponderadas.
    """
    # RSI: média simples
    rsi: Optional[float] = None
    if eur_tech.rsi_14 is not None and jpy_tech.rsi_14 is not None:
        rsi = round((eur_tech.rsi_14 + jpy_tech.rsi_14) / 2, 1)
    else:
        rsi = eur_tech.rsi_14 or jpy_tech.rsi_14

    # Tendência: composição de cross rate
    tend = _TEND_COMPOSITE.get((eur_tech.tendencia, jpy_tech.tendencia), "LATERAL")

    # Bollinger width: média
    bb_w: Optional[float] = None
    if eur_tech.bb_width is not None and jpy_tech.bb_width is not None:
        bb_w = round((eur_tech.bb_width + jpy_tech.bb_width) / 2, 4)
    else:
        bb_w = eur_tech.bb_width or jpy_tech.bb_width

    # Sinal técnico composto
    if bb_w and bb_w < 0.008:
        sinal = "BB_SQUEEZE"
    elif rsi and rsi > 65 and tend == "ALTA":
        sinal = "VENDA"
    elif rsi and rsi < 35 and tend == "BAIXA":
        sinal = "COMPRA"
    else:
        sinal = "NEUTRO"

    logger.info("[EUR/JPY] Tech blendado: rsi=%.1f tend=%s bb_w=%s sinal=%s",
                rsi or 0, tend, bb_w, sinal)

    return TechIndicators(
        sma20=None,  # SMA em unidades diferentes — não blendável diretamente
        sma50=None,
        rsi_14=rsi,
        bb_upper=None,
        bb_lower=None,
        bb_width=bb_w,
        tendencia=tend,
        sinal_tecnico=sinal,
    )
