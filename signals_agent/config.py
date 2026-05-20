import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env.signals na pasta do agente (ou variáveis de ambiente do SO)
_env_path = Path(__file__).parent / ".env.signals"
load_dotenv(_env_path)

RAILWAY_API_URL      = os.getenv("RAILWAY_API_URL", "http://localhost:8000")
SINAIS_API_KEY       = os.getenv("SINAIS_API_KEY", "")
TWS_HOST             = os.getenv("TWS_HOST", "127.0.0.1")
TWS_PORT             = int(os.getenv("TWS_PORT", "7497"))
TWS_CLIENT_ID        = int(os.getenv("TWS_CLIENT_ID", "1"))
SYNC_INTERVAL_MIN    = int(os.getenv("SYNC_INTERVAL_MINUTES", "50"))

# Pares a cobrir. symbol = ticker CME; par = label UI; invert_spot: exibir como 1/spot
PAIRS = [
    {"symbol": "EUR", "par": "EUR/USD", "exchange": "CME", "invert_spot": False},
    {"symbol": "GBP", "par": "GBP/USD", "exchange": "CME", "invert_spot": False},
    {"symbol": "JPY", "par": "USD/JPY", "exchange": "CME", "invert_spot": True},
    # AUD/USD, USD/CAD e USD/CHF removidos por liquidez insuficiente nas opções CME
]

MIN_LIQUID_STRIKES = 5   # mínimo de strikes com bid/ask válidos para gerar sinal
