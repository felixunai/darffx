"""Endpoints de calendário econômico — recebe do agente, serve ao frontend."""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db, get_paid_user, verificar_api_key
from ..models.database import EventoEconomico

router = APIRouter(prefix="/eventos", tags=["eventos"])

# ── Schemas ──────────────────────────────────────────────────────────────────

class EventoPayload(BaseModel):
    event_key:  str
    titulo:     str
    pais:       str
    moeda:      str
    impacto:    str
    evento_em:  str           # "YYYY-MM-DD HH:MM:SS"
    estimativa: Optional[float] = None
    anterior:   Optional[float] = None
    atual:      Optional[float] = None
    unidade:    Optional[str]  = None
    pares:      Optional[str]  = None   # CSV "EUR/USD,USD/JPY"


class EventoOut(BaseModel):
    id:         int
    titulo:     str
    pais:       str
    moeda:      str
    impacto:    str
    evento_em:  str
    estimativa: Optional[float]
    anterior:   Optional[float]
    atual:      Optional[float]
    unidade:    Optional[str]
    pares:      Optional[list[str]]

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/sync", status_code=200)
def sync_eventos(
    eventos: List[EventoPayload],
    _: None = Depends(verificar_api_key),
    db: Session = Depends(get_db),
):
    """Recebe eventos do agente local. Faz upsert por event_key."""
    upserted = 0
    for e in eventos:
        try:
            evento_em = datetime.strptime(e.evento_em[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

        existing = db.query(EventoEconomico).filter_by(event_key=e.event_key).first()
        if existing:
            # Atualiza resultado real quando disponível
            if e.atual is not None:
                existing.atual = e.atual
        else:
            db.add(EventoEconomico(
                event_key  = e.event_key,
                titulo     = e.titulo,
                pais       = e.pais,
                moeda      = e.moeda,
                impacto    = e.impacto,
                evento_em  = evento_em,
                estimativa = e.estimativa,
                anterior   = e.anterior,
                atual      = e.atual,
                unidade    = e.unidade,
                pares      = e.pares,
            ))
            upserted += 1

    db.commit()
    _cleanup_eventos(db)
    return {"ok": True, "upserted": upserted}


@router.get("", response_model=List[EventoOut])
def get_eventos(
    par: Optional[str] = None,
    _: None = Depends(get_paid_user),
    db: Session = Depends(get_db),
):
    """Retorna eventos dos próximos 7 dias (e últimos 2 dias passados para contexto)."""
    agora  = datetime.utcnow()
    inicio = agora - timedelta(days=2)
    fim    = agora + timedelta(days=7)

    q = (
        db.query(EventoEconomico)
        .filter(
            EventoEconomico.evento_em >= inicio,
            EventoEconomico.evento_em <= fim,
        )
        .order_by(EventoEconomico.evento_em)
    )

    rows = q.all()

    result = []
    for r in rows:
        pares_list = [p.strip() for p in (r.pares or "").split(",") if p.strip()]
        if par and par not in pares_list:
            continue
        result.append(EventoOut(
            id         = r.id,
            titulo     = r.titulo,
            pais       = r.pais,
            moeda      = r.moeda,
            impacto    = r.impacto,
            evento_em  = r.evento_em.isoformat() + "Z",
            estimativa = r.estimativa,
            anterior   = r.anterior,
            atual      = r.atual,
            unidade    = r.unidade,
            pares      = pares_list,
        ))

    return result


def _cleanup_eventos(db: Session) -> None:
    """Remove eventos com mais de 14 dias."""
    cutoff = datetime.utcnow() - timedelta(days=14)
    db.query(EventoEconomico).filter(EventoEconomico.evento_em < cutoff).delete(
        synchronize_session=False
    )
    db.commit()
