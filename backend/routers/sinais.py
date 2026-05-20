from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import get_db, get_paid_user, verificar_api_key
from ..models.database import SinalOpcao, User

router = APIRouter(prefix="/sinais", tags=["sinais"])


# ── Schemas de entrada (agente local → Railway) ─────────────────────────────

class SinalPayload(BaseModel):
    par: str
    symbol: str
    expiracao: str          # "YYYY-MM-DD"
    tipo_sinal: str
    strike_principal: Optional[float] = None
    strike_secundario: Optional[float] = None
    premio_call: Optional[float] = None
    premio_put: Optional[float] = None
    custo_total: Optional[float] = None
    delta_call: Optional[float] = None
    delta_put: Optional[float] = None
    gamma: Optional[float] = None
    theta_call: Optional[float] = None
    vega_call: Optional[float] = None
    iv_call: Optional[float] = None
    iv_put: Optional[float] = None
    iv_media: Optional[float] = None
    iv_skew: Optional[float] = None
    spot_price: Optional[float] = None
    volume_call: Optional[int] = None
    volume_put: Optional[int] = None
    oi_call: Optional[int] = None
    oi_put: Optional[int] = None
    score: Optional[float] = None
    recomendacao: Optional[str] = None
    rsi_14: Optional[float] = None
    sma20: Optional[float] = None
    sma50: Optional[float] = None
    bb_width: Optional[float] = None
    tendencia: Optional[str] = None
    pc_ratio: Optional[float] = None
    motivo: Optional[str] = None
    strikes_recomendados: Optional[str] = None
    dte: Optional[int] = None
    prob_profit: Optional[float] = None
    expected_move: Optional[float] = None
    criado_em: Optional[str] = None   # usado pelo backfill para datas retroativas


# ── Schemas de saída (Railway → frontend) ───────────────────────────────────

class SinalOut(BaseModel):
    id: int
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
    spot_price: Optional[float]
    volume_call: Optional[int]
    volume_put: Optional[int]
    oi_call: Optional[int]
    oi_put: Optional[int]
    iv_rank_30d: Optional[float]
    score: Optional[float]
    recomendacao: Optional[str]
    rsi_14: Optional[float]
    sma20: Optional[float]
    sma50: Optional[float]
    bb_width: Optional[float]
    tendencia: Optional[str]
    pc_ratio: Optional[float]
    motivo: Optional[str]
    strikes_recomendados: Optional[str]
    dte: Optional[int]
    prob_profit: Optional[float]
    expected_move: Optional[float]
    criado_em: str

    class Config:
        from_attributes = True


def _recalcular_score(tipo_sinal: str, iv_rank: Optional[float],
                      iv_skew: Optional[float], tendencia: Optional[str],
                      rsi_14: Optional[float], bb_width: Optional[float]) -> tuple[float, str]:
    """Recalcula score/recomendação com o iv_rank real calculado após inserção."""
    if iv_rank is None:
        return 50.0, "NEUTRAL"

    if tipo_sinal in ("straddle", "strangle"):
        if iv_rank > 70:
            score, rec = iv_rank, "SELL"
        elif iv_rank < 30:
            score, rec = 100.0 - iv_rank, "BUY"
        else:
            return 50.0, "NEUTRAL"
        if rec == "BUY" and bb_width and bb_width < 0.008:
            score = min(100.0, score + 20)
        elif rec == "SELL" and rsi_14 and rsi_14 > 65:
            score = min(100.0, score + 10)
        return round(score, 1), rec

    if tipo_sinal == "bull_spread":
        if iv_skew and iv_skew > 0.003:
            score, rec = min(100.0, abs(iv_skew) * 8000), "BULL_SPREAD"
        else:
            return 30.0, "NEUTRAL"
        if tendencia == "ALTA":   score = min(100.0, score + 20)
        elif tendencia == "BAIXA": score = max(10.0,  score - 20)
        if rsi_14 and rsi_14 > 70: score = max(10.0, score - 15)
        return round(score, 1), rec

    if tipo_sinal == "bear_spread":
        if iv_skew and iv_skew < -0.003:
            score, rec = min(100.0, abs(iv_skew) * 8000), "BEAR_SPREAD"
        else:
            return 30.0, "NEUTRAL"
        if tendencia == "BAIXA":  score = min(100.0, score + 20)
        elif tendencia == "ALTA": score = max(10.0,  score - 20)
        if rsi_14 and rsi_14 < 30: score = max(10.0, score - 15)
        return round(score, 1), rec

    return 50.0, "NEUTRAL"


def _calcular_iv_rank(db: Session, par: str, iv_media_atual: Optional[float]) -> Optional[float]:
    """Calcula IV Rank percentual usando min/max dos últimos 30 dias para o par."""
    if iv_media_atual is None:
        return None
    cutoff = datetime.utcnow() - timedelta(days=30)
    resultado = (
        db.query(func.min(SinalOpcao.iv_media), func.max(SinalOpcao.iv_media))
        .filter(SinalOpcao.par == par, SinalOpcao.criado_em >= cutoff, SinalOpcao.iv_media.isnot(None))
        .one()
    )
    iv_min, iv_max = resultado
    if iv_min is None or iv_max is None or iv_max == iv_min:
        return None
    rank = (iv_media_atual - iv_min) / (iv_max - iv_min) * 100
    return round(max(0.0, min(100.0, rank)), 2)


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/sync", status_code=201)
def sync_sinais(
    sinais: List[SinalPayload],
    _: None = Depends(verificar_api_key),
    db: Session = Depends(get_db),
):
    """Recebe lote de sinais do agente local. Autenticado via X-Api-Key."""
    if not sinais:
        raise HTTPException(422, "Lista de sinais vazia.")

    criados = 0
    for s in sinais:
        try:
            expiracao = datetime.strptime(s.expiracao, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(422, f"Data inválida: {s.expiracao}")

        criado_em_val = None
        if s.criado_em:
            try:
                criado_em_val = datetime.fromisoformat(s.criado_em)
            except ValueError:
                pass

        iv_rank = _calcular_iv_rank(db, s.par, s.iv_media)

        # Recalcula score/rec com o IV Rank real (o agente envia score provisório sem rank)
        score_final, rec_final = _recalcular_score(
            s.tipo_sinal, iv_rank, s.iv_skew, s.tendencia, s.rsi_14, s.bb_width
        )
        # Mantém score do agente apenas se o backend não tiver IV Rank suficiente
        if iv_rank is None:
            score_final = s.score or 50.0
            rec_final   = s.recomendacao or "NEUTRAL"

        db.add(SinalOpcao(
            par=s.par,
            symbol=s.symbol,
            expiracao=expiracao,
            tipo_sinal=s.tipo_sinal,
            strike_principal=s.strike_principal,
            strike_secundario=s.strike_secundario,
            premio_call=s.premio_call,
            premio_put=s.premio_put,
            custo_total=s.custo_total,
            delta_call=s.delta_call,
            delta_put=s.delta_put,
            gamma=s.gamma,
            theta_call=s.theta_call,
            vega_call=s.vega_call,
            iv_call=s.iv_call,
            iv_put=s.iv_put,
            iv_media=s.iv_media,
            iv_skew=s.iv_skew,
            spot_price=s.spot_price,
            volume_call=s.volume_call,
            volume_put=s.volume_put,
            oi_call=s.oi_call,
            oi_put=s.oi_put,
            iv_rank_30d=iv_rank,
            score=score_final,
            recomendacao=rec_final,
            rsi_14=s.rsi_14,
            sma20=s.sma20,
            sma50=s.sma50,
            bb_width=s.bb_width,
            tendencia=s.tendencia,
            pc_ratio=s.pc_ratio,
            motivo=s.motivo,
            strikes_recomendados=s.strikes_recomendados,
            dte=s.dte,
            prob_profit=s.prob_profit,
            expected_move=s.expected_move,
            **({"criado_em": criado_em_val} if criado_em_val else {}),
        ))
        criados += 1

    db.commit()
    _cleanup_sinais(db)
    return {"ok": True, "criados": criados}


def _cleanup_sinais(db: Session) -> None:
    """
    Mantém no máximo 1 registro por (par, tipo_sinal, dia) e apaga tudo além de 30 dias.
    Garante histórico suficiente para o IV Rank sem acumular lixo.
    """
    # 1. Apaga registros com mais de 30 dias
    cutoff = datetime.utcnow() - timedelta(days=30)
    db.query(SinalOpcao).filter(SinalOpcao.criado_em < cutoff).delete(synchronize_session=False)

    # 2. Por (par, tipo_sinal, data), mantém apenas o id mais alto (mais recente do dia)
    subq = (
        db.query(func.max(SinalOpcao.id).label("keep_id"))
        .group_by(
            SinalOpcao.par,
            SinalOpcao.tipo_sinal,
            func.date(SinalOpcao.criado_em),
        )
        .subquery()
    )
    keep_ids = [row[0] for row in db.query(subq.c.keep_id).all() if row[0] is not None]

    if keep_ids:
        db.query(SinalOpcao).filter(~SinalOpcao.id.in_(keep_ids)).delete(synchronize_session=False)

    db.commit()


@router.get("/latest", response_model=List[SinalOut])
def get_latest(
    usuario: User = Depends(get_paid_user),
    db: Session = Depends(get_db),
):
    """Retorna o sinal mais recente por par × tipo_sinal."""
    subq = (
        db.query(
            SinalOpcao.par,
            SinalOpcao.tipo_sinal,
            func.max(SinalOpcao.criado_em).label("max_dt"),
        )
        .group_by(SinalOpcao.par, SinalOpcao.tipo_sinal)
        .subquery()
    )
    rows = (
        db.query(SinalOpcao)
        .join(
            subq,
            (SinalOpcao.par == subq.c.par)
            & (SinalOpcao.tipo_sinal == subq.c.tipo_sinal)
            & (SinalOpcao.criado_em == subq.c.max_dt),
        )
        .order_by(SinalOpcao.par, SinalOpcao.tipo_sinal)
        .all()
    )
    return [_to_out(r) for r in rows]


@router.get("", response_model=List[SinalOut])
def get_sinais(
    par: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    usuario: User = Depends(get_paid_user),
    db: Session = Depends(get_db),
):
    """Histórico de sinais com filtros opcionais por par e tipo."""
    q = db.query(SinalOpcao).order_by(SinalOpcao.criado_em.desc())
    if par:
        q = q.filter(SinalOpcao.par == par)
    if tipo:
        q = q.filter(SinalOpcao.tipo_sinal == tipo)
    return [_to_out(r) for r in q.limit(limit).all()]


def _to_out(s: SinalOpcao) -> SinalOut:
    return SinalOut(
        id=s.id,
        par=s.par,
        symbol=s.symbol,
        expiracao=s.expiracao.isoformat() if s.expiracao else "",
        tipo_sinal=s.tipo_sinal,
        strike_principal=s.strike_principal,
        strike_secundario=s.strike_secundario,
        premio_call=s.premio_call,
        premio_put=s.premio_put,
        custo_total=s.custo_total,
        delta_call=s.delta_call,
        delta_put=s.delta_put,
        gamma=s.gamma,
        theta_call=s.theta_call,
        vega_call=s.vega_call,
        iv_call=s.iv_call,
        iv_put=s.iv_put,
        iv_media=s.iv_media,
        iv_skew=s.iv_skew,
        spot_price=s.spot_price,
        volume_call=s.volume_call,
        volume_put=s.volume_put,
        oi_call=s.oi_call,
        oi_put=s.oi_put,
        iv_rank_30d=s.iv_rank_30d,
        score=s.score,
        recomendacao=s.recomendacao,
        rsi_14=s.rsi_14,
        sma20=s.sma20,
        sma50=s.sma50,
        bb_width=s.bb_width,
        tendencia=s.tendencia,
        pc_ratio=s.pc_ratio,
        motivo=s.motivo,
        strikes_recomendados=s.strikes_recomendados,
        dte=s.dte,
        prob_profit=s.prob_profit,
        expected_move=s.expected_move,
        criado_em=(s.criado_em.isoformat() + "Z") if s.criado_em else "",
    )
