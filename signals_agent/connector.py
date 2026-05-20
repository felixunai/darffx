import logging
from ib_insync import IB

from .config import TWS_HOST, TWS_PORT, TWS_CLIENT_ID

logger = logging.getLogger(__name__)

_ib: IB | None = None


def get_ib() -> IB:
    """Retorna instância IB conectada. Reconecta se necessário."""
    global _ib
    if _ib is None:
        _ib = IB()
    if not _ib.isConnected():
        logger.info("Conectando ao TWS em %s:%s (clientId=%s)…", TWS_HOST, TWS_PORT, TWS_CLIENT_ID)
        _ib.connect(TWS_HOST, TWS_PORT, clientId=TWS_CLIENT_ID, readonly=True, timeout=20)
        _ib.reqTimeout = 30   # requisições travam no máximo 30 s antes de lançar exceção
        logger.info("Conectado ao TWS.")
    return _ib


def disconnect():
    global _ib
    if _ib and _ib.isConnected():
        _ib.disconnect()
        logger.info("Desconectado do TWS.")
