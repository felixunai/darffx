"""Gera sinais de operações estruturadas combinando análise de IV e análise técnica."""

import logging
from dataclasses import dataclass, field
from typing import Optional

from .chain_fetcher import OptionLeg, OptionsChain
from .tech_analysis import TechIndicators

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    par: str
    symbol: str
    expiracao: str
    tipo_sinal: str
    strike_principal: Optional[float]
    strike_secundario: Optional[float]
    premio_call: Optional[float]
    premio_put: Optional[float]
    custo_total: Optional[float]
    delta_call: Optional[float]
    delta_put: Optional[float]
    gamma: Optional[float]
    theta_call: Optional[float]
    vega_call: Optional[float]
    iv_call: Optional[float]
    iv_put: Optional[float]
    iv_media: Optional[float]
    iv_skew: Optional[float]
    spot_price: float
    volume_call: Optional[int]
    volume_put: Optional[int]
    oi_call: Optional[int]
    oi_put: Optional[int]
    score: Optional[float]
    recomendacao: str
    # Campos enriquecidos
    motivo: str = ""
    strikes_recomendados: str = ""
    rsi_14: Optional[float] = None
    sma20: Optional[float] = None
    sma50: Optional[float] = None
    bb_width: Optional[float] = None
    tendencia: str = "LATERAL"
    pc_ratio: Optional[float] = None
    # Métricas de risco para strangle vendido
    dte: int = 0
    prob_profit: Optional[float] = None   # 0-100 %
    expected_move: Optional[float] = None  # movimento 1σ esperado até vencimento


def _expiry_to_iso(expiry: str) -> str:
    return f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:]}"


def _find_atm(legs: list[OptionLeg], spot: float) -> Optional[OptionLeg]:
    return min(legs, key=lambda l: abs(l.strike - spot)) if legs else None


def _find_otm_call(calls: list[OptionLeg], atm_strike: float) -> Optional[OptionLeg]:
    above = [c for c in calls if c.strike > atm_strike]
    return above[0] if above else None


def _find_otm_put(puts: list[OptionLeg], atm_strike: float) -> Optional[OptionLeg]:
    below = [p for p in puts if p.strike < atm_strike]
    return below[-1] if below else None


# Delta alvo para strangle vendido semanal: 15-20 delta
STRANGLE_DELTA_TARGET = 0.16


def _find_delta_call(calls: list[OptionLeg], atm_strike: float,
                     target_delta: float = STRANGLE_DELTA_TARGET) -> Optional[OptionLeg]:
    """Busca a call OTM cujo delta é mais próximo do alvo (ex: 0.16 = delta 16)."""
    otm = [c for c in calls if c.strike > atm_strike and c.delta is not None and c.delta > 0]
    if not otm:
        return _find_otm_call(calls, atm_strike)
    return min(otm, key=lambda c: abs((c.delta or 0) - target_delta))


def _find_delta_put(puts: list[OptionLeg], atm_strike: float,
                    target_delta: float = STRANGLE_DELTA_TARGET) -> Optional[OptionLeg]:
    """Busca a put OTM cujo delta absoluto é mais próximo do alvo (ex: 0.16)."""
    otm = [p for p in puts if p.strike < atm_strike and p.delta is not None and p.delta < 0]
    if not otm:
        return _find_otm_put(puts, atm_strike)
    return min(otm, key=lambda p: abs(abs(p.delta or 0) - target_delta))


def _calc_pop(delta_call: Optional[float], delta_put: Optional[float]) -> Optional[float]:
    """
    POP do strangle vendido ≈ 1 - |delta_call| - |delta_put|.
    Aproximação de Black-Scholes: delta ≈ probabilidade de ser exercido.
    """
    if delta_call is None or delta_put is None:
        return None
    pop = 1.0 - abs(delta_call) - abs(delta_put)
    return round(max(0.0, min(1.0, pop)) * 100, 1)


def _calc_expected_move(spot: float, iv: Optional[float], dte: int) -> Optional[float]:
    """Movimento 1σ esperado até vencimento: spot × IV × √(DTE/365)."""
    if not iv or dte <= 0:
        return None
    return round(spot * iv * (dte / 365) ** 0.5, 5)


def _pc_ratio(chain: OptionsChain) -> Optional[float]:
    vol_call = sum(c.volume for c in chain.calls)
    vol_put  = sum(p.volume for p in chain.puts)
    if vol_call > 0:
        return round(vol_put / vol_call, 2)
    return None


def _fmt(v: Optional[float], dec: int = 4) -> str:
    if v is None:
        return "N/D"
    # Pares invertidos (USD/JPY ~158, USD/CAD ~1.37) usam menos casas decimais
    if v >= 10.0:
        return f"{v:.2f}"
    if v >= 1.0:
        return f"{v:.4f}"
    return f"{v:.{dec}f}"


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score_vol(iv_rank: Optional[float], iv_media: Optional[float],
               tech: TechIndicators, tipo: str) -> tuple[float, str]:
    """
    Pontuação para estruturas de volatilidade (straddle / strangle).
    Combina IV rank + sinal técnico.
    """
    # Base: IV absoluta quando rank ainda não disponível
    if iv_rank is None:
        if iv_media is not None:
            pct = iv_media * 100
            if pct < 5.0:
                base_score, base_rec = min(100.0, (5.0 - pct) / 5.0 * 100), "BUY"
            elif pct > 12.0:
                base_score, base_rec = min(100.0, (pct - 12.0) / 8.0 * 100), "SELL"
            else:
                base_score, base_rec = 50.0, "NEUTRAL"
        else:
            return 50.0, "NEUTRAL"
    else:
        if iv_rank > 70:
            base_score, base_rec = iv_rank, "SELL"
        elif iv_rank < 30:
            base_score, base_rec = 100 - iv_rank, "BUY"
        else:
            base_score, base_rec = 50.0, "NEUTRAL"

    # Boost técnico
    bonus = 0.0
    if base_rec == "BUY" and tech.sinal_tecnico == "BB_SQUEEZE":
        bonus = 20.0   # squeeze confirma compra de vol
    elif base_rec == "SELL" and tech.sinal_tecnico == "VENDA":
        bonus = 10.0   # sobrecomprado confirma venda de vol
    elif base_rec == "BUY" and tech.sinal_tecnico == "VENDA":
        bonus = -10.0  # contradição — reduz confiança

    return round(min(100.0, base_score + bonus), 1), base_rec


def _score_spread(iv_skew: Optional[float], tech: TechIndicators,
                  tipo: str) -> tuple[float, str]:
    """
    Pontuação para spreads direcionais (bull_spread / bear_spread).
    Combina skew de IV + tendência técnica.
    """
    if iv_skew is None:
        return 50.0, "NEUTRAL"

    if tipo == "bull_spread":
        # Skew positivo (calls mais caras) = mercado precificando alta
        base = min(100.0, abs(iv_skew) * 8000) if iv_skew > 0.003 else 30.0
        rec  = "BULL_SPREAD" if iv_skew > 0.003 else "NEUTRAL"
        # Confirmação técnica
        if tech.tendencia == "ALTA":
            base = min(100.0, base + 20)
        elif tech.tendencia == "BAIXA":
            base = max(10.0, base - 20)
        if tech.rsi_14 and tech.rsi_14 > 70:
            base = max(10.0, base - 15)   # sobrecomprado → spread bull mais arriscado
    else:  # bear_spread
        base = min(100.0, abs(iv_skew) * 8000) if iv_skew < -0.003 else 30.0
        rec  = "BEAR_SPREAD" if iv_skew < -0.003 else "NEUTRAL"
        if tech.tendencia == "BAIXA":
            base = min(100.0, base + 20)
        elif tech.tendencia == "ALTA":
            base = max(10.0, base - 20)
        if tech.rsi_14 and tech.rsi_14 < 30:
            base = max(10.0, base - 15)   # sobrevendido → spread bear mais arriscado

    return round(base, 1), rec


# ── Geração de motivo ─────────────────────────────────────────────────────────

def _motivo_straddle(rec: str, score: float, iv_media: Optional[float],
                     iv_rank: Optional[float], tech: TechIndicators,
                     custo: Optional[float], atm: float, spot: float,
                     invert_spot: bool = False) -> str:
    partes = []

    # IV
    if iv_rank is not None:
        partes.append(f"IV Rank {iv_rank:.0f}% ({('cara' if iv_rank > 70 else 'barata' if iv_rank < 30 else 'neutra')})")
    elif iv_media is not None:
        partes.append(f"IV atual {iv_media*100:.2f}% ({('acima' if iv_media*100 > 10 else 'abaixo')} da média histórica de Forex)")

    # Técnico
    if tech.sinal_tecnico == "BB_SQUEEZE":
        partes.append(f"Bandas de Bollinger comprimidas (width {tech.bb_width:.3f}) → movimento explosivo esperado")
    if tech.rsi_14:
        if tech.rsi_14 > 65:
            partes.append(f"RSI {tech.rsi_14:.0f} sobrecomprado")
        elif tech.rsi_14 < 35:
            partes.append(f"RSI {tech.rsi_14:.0f} sobrevendido")
    if tech.tendencia != "LATERAL":
        partes.append(f"Tendência {tech.tendencia} (spot {'>' if tech.tendencia == 'ALTA' else '<'} SMA20 {'>' if tech.tendencia == 'ALTA' else '<'} SMA50)")

    # Ação + breakeven
    def _be_straddle(atm_val: float, custo_val: float):
        """Breakeven considerando convenção de cotação (normal ou invertida)."""
        if invert_spot and atm_val > 0:
            atm_raw = 1.0 / atm_val
            up = round(1.0 / max(atm_raw - custo_val, 1e-10), 2)
            dn = round(1.0 / (atm_raw + custo_val), 2)
        else:
            up = round(atm_val + custo_val, 5)
            dn = round(atm_val - custo_val, 5)
        return up, dn

    if rec == "BUY":
        acao = "COMPRAR STRADDLE"
        if custo:
            be_up, be_dn = _be_straddle(atm, custo)
            partes.append(f"→ {acao}: Call @{_fmt(atm)} + Put @{_fmt(atm)} | Custo: {_fmt(custo)} | Breakeven: >{be_up} ou <{be_dn}")
        else:
            partes.append(f"→ {acao}: Call @{_fmt(atm)} + Put @{_fmt(atm)}")
    elif rec == "SELL":
        acao = "VENDER STRADDLE"
        if custo:
            be_up, be_dn = _be_straddle(atm, custo)
            partes.append(f"→ {acao}: Call @{_fmt(atm)} + Put @{_fmt(atm)} | Crédito: {_fmt(custo)} | Ganho máx se spot entre {be_dn}~{be_up}")
        else:
            partes.append(f"→ {acao}: Call @{_fmt(atm)} + Put @{_fmt(atm)}")
    else:
        partes.append(f"IV e técnico neutros — aguardar catalisador. Spot atual: {_fmt(spot)}")

    return " | ".join(partes)


def _motivo_strangle(rec: str, iv_rank: Optional[float], iv_media: Optional[float],
                     tech: TechIndicators, custo: Optional[float],
                     call_leg: OptionLeg, put_leg: OptionLeg,
                     dte: int = 0, pop: Optional[float] = None,
                     expected_move: Optional[float] = None,
                     spot: Optional[float] = None,
                     invert_spot: bool = False) -> str:
    partes = []
    if iv_rank is not None:
        partes.append(f"IV Rank {iv_rank:.0f}%")
    elif iv_media:
        partes.append(f"IV {iv_media*100:.2f}%")
    if dte:
        partes.append(f"DTE={dte}")
    if pop is not None:
        partes.append(f"POP≈{pop:.0f}% (prob. de lucro)")
    if expected_move and spot:
        be_range_lo = round(spot - expected_move, 2 if spot >= 1.0 else 5)
        be_range_hi = round(spot + expected_move, 2 if spot >= 1.0 else 5)
        partes.append(f"Mov. esperado ±{_fmt(expected_move)} → faixa {be_range_lo}~{be_range_hi}")
    if tech.sinal_tecnico == "BB_SQUEEZE":
        partes.append("Bollinger squeeze — ATENÇÃO: expansão de vol esperada, risco para strangle vendido")
    elif tech.tendencia != "LATERAL":
        partes.append(f"Tendência {tech.tendencia} — monitorar breakout")

    def _be_strangle(c_strike: float, p_strike: float, custo_val: float):
        """Breakeven de strangle: call_strike ± custo e put_strike ∓ custo (convenção normal ou invertida)."""
        if invert_spot and c_strike > 0 and p_strike > 0:
            # Para pares invertidos: BE call = 1/(1/c_strike - custo), BE put = 1/(1/p_strike + custo)
            be_up = round(1.0 / max(1.0/c_strike - custo_val, 1e-10), 2)
            be_dn = round(1.0 / (1.0/p_strike + custo_val), 2)
        else:
            be_up = round(c_strike + custo_val, 5)
            be_dn = round(p_strike - custo_val, 5)
        return be_up, be_dn

    if rec == "SELL":
        if custo:
            be_up, be_dn = _be_strangle(call_leg.strike, put_leg.strike, custo)
            partes.append(
                f"→ VENDER STRANGLE: Call @{_fmt(call_leg.strike)} + Put @{_fmt(put_leg.strike)}"
                f" | Crédito: {_fmt(custo)} | Lucro máx se spot entre {be_dn}~{be_up}"
            )
        else:
            partes.append(f"→ VENDER STRANGLE: Call @{_fmt(call_leg.strike)} + Put @{_fmt(put_leg.strike)}")
    elif rec == "BUY":
        if custo:
            be_up, be_dn = _be_strangle(call_leg.strike, put_leg.strike, custo)
            partes.append(
                f"→ COMPRAR STRANGLE: Call @{_fmt(call_leg.strike)} + Put @{_fmt(put_leg.strike)}"
                f" | Custo: {_fmt(custo)} | Breakeven: >{be_up} ou <{be_dn}"
            )
        else:
            partes.append(f"→ COMPRAR STRANGLE: Call @{_fmt(call_leg.strike)} + Put @{_fmt(put_leg.strike)}")
    else:
        partes.append("IV neutra — aguardar IV Rank > 70 (vender) ou < 30 (comprar).")
    return " | ".join(partes)


def _motivo_bull_spread(score: float, iv_skew: Optional[float], tech: TechIndicators,
                        atm_call: OptionLeg, otm_call: OptionLeg,
                        invert_spot: bool = False) -> str:
    partes = []
    if iv_skew and iv_skew > 0:
        partes.append(f"Skew de calls +{iv_skew*100:.2f}% (calls mais caras → mercado precifica alta)")
    if tech.tendencia == "ALTA":
        partes.append(f"Tendência de ALTA confirmada (SMA20 > SMA50)")
    if tech.rsi_14:
        if tech.rsi_14 < 65:
            partes.append(f"RSI {tech.rsi_14:.0f} sem sobrecompra — upside ainda disponível")
        else:
            partes.append(f"RSI {tech.rsi_14:.0f} elevado — risco de reversão")
    net = round((atm_call.mid or 0) - (otm_call.mid or 0), 5)
    if net and not invert_spot:
        lucro = round(otm_call.strike - atm_call.strike - net, 5)
        be    = round(atm_call.strike + net, 5)
        extra = f" | Custo líq: {_fmt(net)} | Breakeven: {_fmt(be)} | Max lucro: {_fmt(lucro)}"
    elif net:
        # Para pares invertidos o spread e breakeven ficam na convenção do par
        extra = f" | Custo líq: {_fmt(net)}"
    else:
        extra = ""
    partes.append(
        f"→ BULL CALL SPREAD: Compra Call @{_fmt(atm_call.strike)}, Vende Call @{_fmt(otm_call.strike)}{extra}"
    )
    return " | ".join(partes)


def _motivo_bear_spread(score: float, iv_skew: Optional[float], tech: TechIndicators,
                        atm_put: OptionLeg, otm_put: OptionLeg,
                        invert_spot: bool = False) -> str:
    partes = []
    if iv_skew and iv_skew < 0:
        partes.append(f"Skew de puts {iv_skew*100:.2f}% (puts mais caras → hedge comprado / pressão baixista)")
    if tech.tendencia == "BAIXA":
        partes.append("Tendência de BAIXA confirmada (SMA20 < SMA50)")
    if tech.rsi_14:
        if tech.rsi_14 > 35:
            partes.append(f"RSI {tech.rsi_14:.0f} sem sobrevenda — downside disponível")
        else:
            partes.append(f"RSI {tech.rsi_14:.0f} baixo — risco de bounce")
    net = round((atm_put.mid or 0) - (otm_put.mid or 0), 5)
    if net and not invert_spot:
        lucro = round(atm_put.strike - otm_put.strike - net, 5)
        be    = round(atm_put.strike - net, 5)
        extra = f" | Custo líq: {_fmt(net)} | Breakeven: {_fmt(be)} | Max lucro: {_fmt(lucro)}"
    elif net:
        extra = f" | Custo líq: {_fmt(net)}"
    else:
        extra = ""
    partes.append(
        f"→ BEAR PUT SPREAD: Compra Put @{_fmt(atm_put.strike)}, Vende Put @{_fmt(otm_put.strike)}{extra}"
    )
    return " | ".join(partes)


# ── Montagem de Signal ────────────────────────────────────────────────────────

def _base_signal(chain: OptionsChain, tipo: str,
                 call: OptionLeg, put: OptionLeg,
                 tech: TechIndicators,
                 strike_sec: Optional[float] = None) -> Signal:
    iv_c   = call.iv
    iv_p   = put.iv
    iv_med = ((iv_c or 0) + (iv_p or 0)) / 2 if (iv_c or iv_p) else None
    iv_med = iv_med if iv_med and iv_med > 0 else None
    iv_sk  = round((iv_c or 0) - (iv_p or 0), 6) if (iv_c and iv_p) else None
    custo  = round((call.mid or 0) + (put.mid or 0), 6) or None
    pc     = _pc_ratio(chain)
    pop    = _calc_pop(call.delta, put.delta)
    em     = _calc_expected_move(chain.spot, iv_med, chain.dte)

    return Signal(
        par=chain.par, symbol=chain.symbol,
        expiracao=_expiry_to_iso(chain.expiry),
        tipo_sinal=tipo,
        strike_principal=call.strike,
        strike_secundario=strike_sec,
        premio_call=call.mid or None,
        premio_put=put.mid or None,
        custo_total=custo,
        delta_call=call.delta, delta_put=put.delta,
        gamma=call.gamma, theta_call=call.theta, vega_call=call.vega,
        iv_call=iv_c, iv_put=iv_p,
        iv_media=round(iv_med, 6) if iv_med else None,
        iv_skew=iv_sk,
        spot_price=chain.spot,
        volume_call=call.volume or None,
        volume_put=put.volume or None,
        oi_call=call.open_interest or None,
        oi_put=put.open_interest or None,
        score=50.0, recomendacao="NEUTRAL",
        rsi_14=tech.rsi_14, sma20=tech.sma20, sma50=tech.sma50,
        bb_width=tech.bb_width, tendencia=tech.tendencia,
        pc_ratio=pc,
        dte=chain.dte,
        prob_profit=pop,
        expected_move=em,
    )


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def generate_signals(chain: OptionsChain, tech: TechIndicators) -> list[Signal]:
    spot     = chain.spot
    calls    = chain.calls
    puts     = chain.puts
    inv      = chain.invert_spot  # True para USD/JPY, USD/CAD

    atm_call = _find_atm(calls, spot)
    atm_put  = _find_atm(puts,  spot)
    if not atm_call or not atm_put:
        logger.warning("[%s] ATM não encontrado.", chain.symbol)
        return []

    otm_call = _find_otm_call(calls, atm_call.strike)
    otm_put  = _find_otm_put(puts,  atm_put.strike)
    signals: list[Signal] = []

    # ── Straddle ──
    s = _base_signal(chain, "straddle", atm_call, atm_put, tech)
    s.score, s.recomendacao = _score_vol(None, s.iv_media, tech, "straddle")
    s.strikes_recomendados  = f"Call @{_fmt(atm_call.strike)} + Put @{_fmt(atm_put.strike)} (ATM)"
    s.motivo = _motivo_straddle(s.recomendacao, s.score, s.iv_media, None, tech,
                                s.custo_total, atm_call.strike, spot, invert_spot=inv)
    signals.append(s)

    # ── Strangle (delta-based: alvo delta ~16 para strangle vendido semanal) ──
    delta_call = _find_delta_call(calls, atm_call.strike)
    delta_put  = _find_delta_put(puts,  atm_put.strike)
    if delta_call and delta_put:
        s = _base_signal(chain, "strangle", delta_call, delta_put, tech,
                         strike_sec=delta_put.strike)
        s.score, s.recomendacao = _score_vol(None, s.iv_media, tech, "strangle")
        d_c = abs(delta_call.delta or 0)
        d_p = abs(delta_put.delta or 0)
        s.strikes_recomendados = (
            f"Vende Call @{_fmt(delta_call.strike)} (Δ{d_c:.2f}) + "
            f"Vende Put @{_fmt(delta_put.strike)} (Δ{d_p:.2f}) | "
            f"DTE={chain.dte} | POP≈{s.prob_profit:.0f}%" if s.prob_profit else
            f"Vende Call @{_fmt(delta_call.strike)} + Vende Put @{_fmt(delta_put.strike)} | DTE={chain.dte}"
        )
        s.motivo = _motivo_strangle(s.recomendacao, None, s.iv_media, tech,
                                    s.custo_total, delta_call, delta_put,
                                    dte=chain.dte, pop=s.prob_profit,
                                    expected_move=s.expected_move, spot=chain.spot,
                                    invert_spot=inv)
        signals.append(s)

    # ── Bull Call Spread ──
    if otm_call:
        s = _base_signal(chain, "bull_spread", atm_call, atm_put, tech,
                         strike_sec=otm_call.strike)
        s.score, s.recomendacao = _score_spread(s.iv_skew, tech, "bull_spread")
        s.strikes_recomendados  = f"Compra Call @{_fmt(atm_call.strike)} + Vende Call @{_fmt(otm_call.strike)}"
        s.motivo = _motivo_bull_spread(s.score, s.iv_skew, tech, atm_call, otm_call, invert_spot=inv)
        signals.append(s)

    # ── Bear Put Spread ──
    if otm_put:
        s = _base_signal(chain, "bear_spread", atm_call, atm_put, tech,
                         strike_sec=otm_put.strike)
        s.score, s.recomendacao = _score_spread(s.iv_skew, tech, "bear_spread")
        s.strikes_recomendados  = f"Compra Put @{_fmt(atm_put.strike)} + Vende Put @{_fmt(otm_put.strike)}"
        s.motivo = _motivo_bear_spread(s.score, s.iv_skew, tech, atm_put, otm_put, invert_spot=inv)
        signals.append(s)

    logger.info("[%s] %d sinais gerados.", chain.symbol, len(signals))
    return signals
