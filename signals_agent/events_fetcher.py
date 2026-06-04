"""Busca o calendário econômico semanal via Finnhub e mapeia para pares Forex."""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import httpx

from .config import FINNHUB_API_KEY

logger = logging.getLogger(__name__)

# Países cujos dados movem cada moeda
_COUNTRY_CURRENCY: dict[str, str] = {
    "US": "USD",
    "EU": "EUR", "DE": "EUR", "FR": "EUR", "IT": "EUR",
    "ES": "EUR", "PT": "EUR", "BE": "EUR", "NL": "EUR",
    "GB": "GBP",
    "JP": "JPY",
    "AU": "AUD", "NZ": "NZD", "CA": "CAD", "CH": "CHF",
}

# Moedas que aparecem em cada par monitorado
_CURRENCY_PAIRS: dict[str, list[str]] = {
    "USD": ["EUR/USD", "GBP/USD", "USD/JPY", "EUR/JPY"],
    "EUR": ["EUR/USD", "EUR/JPY"],
    "GBP": ["GBP/USD"],
    "JPY": ["USD/JPY", "EUR/JPY"],
}

# Eventos de baixo impacto que não vale exibir mesmo com impact="medium"
_SKIP_KEYWORDS = {
    "4-week", "8-week", "13-week", "26-week", "52-week",
    "bill", "t-bill", "bond auction", "note auction",
}


@dataclass
class EconomicEvent:
    event_key: str            # hash único para deduplicação
    titulo: str
    pais: str
    moeda: str
    impacto: str              # "high" | "medium" | "low"
    evento_em: str            # ISO datetime "YYYY-MM-DD HH:MM:SS"
    estimativa: Optional[float]
    anterior: Optional[float]
    atual: Optional[float]
    unidade: Optional[str]
    pares: list[str] = field(default_factory=list)


def _event_key(country: str, event: str, time: str) -> str:
    raw = f"{country}|{event}|{time}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _pairs_for_country(country: str) -> list[str]:
    moeda = _COUNTRY_CURRENCY.get(country.upper())
    if not moeda:
        return []
    return _CURRENCY_PAIRS.get(moeda, [])


def _should_skip(title: str) -> bool:
    tl = title.lower()
    return any(kw in tl for kw in _SKIP_KEYWORDS)


def fetch_events(days_ahead: int = 7) -> list[EconomicEvent]:
    """
    Retorna eventos de alto/médio impacto para os próximos `days_ahead` dias.
    Requer FINNHUB_API_KEY no .env.signals. Devolve [] silenciosamente se sem chave.
    """
    if not FINNHUB_API_KEY:
        logger.debug("FINNHUB_API_KEY não configurado — calendário desativado.")
        return []

    today = date.today()
    end   = today + timedelta(days=days_ahead)
    url   = "https://finnhub.io/api/v1/calendar/economic"
    params = {
        "from":  today.isoformat(),
        "to":    end.isoformat(),
        "token": FINNHUB_API_KEY,
    }

    try:
        resp = httpx.get(url, params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json().get("economicCalendar", [])
    except Exception as e:
        logger.warning("Erro ao buscar calendário econômico: %s", e)
        return []

    events: list[EconomicEvent] = []
    for item in raw:
        impacto = (item.get("impact") or "low").lower()
        if impacto != "high":
            continue

        country = (item.get("country") or "").upper()
        titulo  = item.get("event") or ""
        if not titulo or _should_skip(titulo):
            continue

        moeda = _COUNTRY_CURRENCY.get(country, "")
        pares = _pairs_for_country(country)
        if not pares:
            continue

        events.append(EconomicEvent(
            event_key  = _event_key(country, titulo, item.get("time", "")),
            titulo     = titulo,
            pais       = country,
            moeda      = moeda,
            impacto    = impacto,
            evento_em  = item.get("time") or "",
            estimativa = item.get("estimate"),
            anterior   = item.get("prev"),
            atual      = item.get("actual"),
            unidade    = item.get("unit"),
            pares      = pares,
        ))

    logger.info("Calendário econômico: %d eventos (alto/médio impacto) para os próx. %d dias.",
                len(events), days_ahead)
    return events
