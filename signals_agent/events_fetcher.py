"""Busca o calendário econômico semanal via Finnhub e mapeia para pares Forex."""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import httpx

from .config import FINNHUB_API_KEY

logger = logging.getLogger(__name__)

# Apenas países/regiões cujos dados movem os pares que monitoramos.
# Intencionalmente excluímos DE, FR, IT, ES individuais — o que importa
# para EUR/USD é o agregado da Eurozone (EU), não dados de país específico.
_COUNTRY_CURRENCY: dict[str, str] = {
    "US": "USD",
    "EU": "EUR",   # Eurozone aggregate
    "GB": "GBP",
    "JP": "JPY",
}

_CURRENCY_PAIRS: dict[str, list[str]] = {
    "USD": ["EUR/USD", "GBP/USD", "USD/JPY", "EUR/JPY"],
    "EUR": ["EUR/USD", "EUR/JPY"],
    "GBP": ["GBP/USD"],
    "JPY": ["USD/JPY", "EUR/JPY"],
}

# Whitelist: evento só entra se o título contiver pelo menos uma dessas strings.
# Foco em dados que realmente movem o câmbio — exclui speeches de membros
# do Fed (exceto Powell), inventários de petróleo, hipotecas, etc.
_KEEP_KEYWORDS = frozenset({
    # Decisões de política monetária
    "interest rate",
    "monetary policy",
    "fomc",
    "fed funds rate",
    # Emprego (EUA)
    "nonfarm payroll",
    "non farm payroll",
    "non-farm payroll",
    "unemployment rate",
    "initial jobless claims",
    "average hourly earnings",
    # Inflação
    "cpi",
    "inflation rate",
    "core inflation",
    "consumer price",
    "pce",
    "producer price",
    "ppi",
    # Crescimento
    "gdp",
    "gross domestic product",
    # Vendas ao varejo (indicador de consumo)
    "retail sales",
    # Presidentes/Chairs dos bancos centrais apenas
    "powell",
    "lagarde",
    "ueda",
    "bailey",
})


@dataclass
class EconomicEvent:
    event_key: str
    titulo: str
    pais: str
    moeda: str
    impacto: str       # sempre "high"
    evento_em: str     # "YYYY-MM-DD HH:MM:SS"
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


def _is_relevant(title: str) -> bool:
    tl = title.lower()
    return any(kw in tl for kw in _KEEP_KEYWORDS)


def fetch_events(days_ahead: int = 7) -> list[EconomicEvent]:
    """
    Retorna eventos de alto impacto para os próximos `days_ahead` dias,
    filtrados por país relevante e tipo de dado que move o câmbio.
    Requer FINNHUB_API_KEY no .env.signals.
    """
    if not FINNHUB_API_KEY:
        logger.debug("FINNHUB_API_KEY não configurado — calendário desativado.")
        return []

    today  = date.today()
    end    = today + timedelta(days=days_ahead)
    params = {
        "from":  today.isoformat(),
        "to":    end.isoformat(),
        "token": FINNHUB_API_KEY,
    }

    try:
        resp = httpx.get(
            "https://finnhub.io/api/v1/calendar/economic",
            params=params, timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json().get("economicCalendar", [])
    except Exception as e:
        logger.warning("Erro ao buscar calendário econômico: %s", e)
        return []

    events: list[EconomicEvent] = []
    for item in raw:
        if (item.get("impact") or "").lower() != "high":
            continue

        country = (item.get("country") or "").upper()
        pares   = _pairs_for_country(country)
        if not pares:
            continue

        titulo = (item.get("event") or "").strip()
        if not titulo or not _is_relevant(titulo):
            continue

        events.append(EconomicEvent(
            event_key  = _event_key(country, titulo, item.get("time", "")),
            titulo     = titulo,
            pais       = country,
            moeda      = _COUNTRY_CURRENCY[country],
            impacto    = "high",
            evento_em  = item.get("time") or "",
            estimativa = item.get("estimate"),
            anterior   = item.get("prev"),
            atual      = item.get("actual"),
            unidade    = item.get("unit"),
            pares      = pares,
        ))

    logger.info("Calendário: %d eventos relevantes para os próximos %d dias.", len(events), days_ahead)
    return events
