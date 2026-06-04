"""Envia sinais e eventos econômicos para o backend no Railway."""

import logging
import math
from dataclasses import asdict

import httpx

from .config import RAILWAY_API_URL, SINAIS_API_KEY
from .events_fetcher import EconomicEvent
from .signal_engine import Signal

logger = logging.getLogger(__name__)

TIMEOUT = 30  # segundos


def _sanitize(obj):
    """Substitui nan/inf por None recursivamente — JSON não aceita esses valores."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def push_signals(signals: list[Signal], dry_run: bool = False,
                 backfill: bool = False) -> bool:
    """
    Faz POST de todos os sinais de uma rodada para o backend.
    Se dry_run=True, apenas loga sem enviar.
    Se backfill=True, inclui criado_em_override no payload.
    Retorna True se bem-sucedido.
    """
    if not signals:
        logger.info("Nenhum sinal para enviar.")
        return True

    payload = []
    for s in signals:
        d = _sanitize(asdict(s))
        # Remove campos internos que não pertencem ao schema
        d.pop("_criado_em_override", None)
        if backfill and hasattr(s, "_criado_em_override"):
            d["criado_em"] = s._criado_em_override  # type: ignore[attr-defined]
        payload.append(d)

    if dry_run:
        logger.info("[DRY-RUN] %d sinais (não enviados):", len(payload))
        for s in payload:
            logger.info("  %s | %s | rec=%s | score=%.1f | tend=%s | rsi=%.1f | strikes=%s",
                        s["par"], s["tipo_sinal"], s["recomendacao"], s.get("score") or 0,
                        s.get("tendencia") or "—",
                        s.get("rsi_14") or 0,
                        s.get("strikes_recomendados") or "—")
            if s.get("motivo"):
                logger.info("    motivo: %s", s["motivo"])
        return True

    url = f"{RAILWAY_API_URL.rstrip('/')}/sinais/sync"
    headers = {"X-Api-Key": SINAIS_API_KEY, "Content-Type": "application/json"}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Railway: %d sinais gravados.", data.get("criados", "?"))
        return True
    except httpx.HTTPStatusError as e:
        logger.error("Erro HTTP ao enviar sinais: %s — %s", e.response.status_code, e.response.text)
    except Exception as e:
        logger.error("Falha ao conectar ao Railway: %s", e)
    return False


def push_events(events: list[EconomicEvent]) -> bool:
    """Envia lista de eventos econômicos para POST /eventos/sync."""
    if not events:
        return True

    payload = []
    for e in events:
        payload.append({
            "event_key":  e.event_key,
            "titulo":     e.titulo,
            "pais":       e.pais,
            "moeda":      e.moeda,
            "impacto":    e.impacto,
            "evento_em":  e.evento_em,
            "estimativa": e.estimativa,
            "anterior":   e.anterior,
            "atual":      e.atual,
            "unidade":    e.unidade,
            "pares":      ",".join(e.pares),
        })

    url     = f"{RAILWAY_API_URL.rstrip('/')}/eventos/sync"
    headers = {"X-Api-Key": SINAIS_API_KEY, "Content-Type": "application/json"}
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Calendário: %d eventos gravados.", data.get("upserted", "?"))
        return True
    except Exception as e:
        logger.warning("Falha ao enviar eventos econômicos: %s", e)
    return False
