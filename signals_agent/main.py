"""
Agente local de sinais de opções Forex (IBKR/CME).

Uso:
    python -m signals_agent.main              # modo normal (loop a cada 15 min)
    python -m signals_agent.main --dry-run    # calcula e loga, sem enviar
    python -m signals_agent.main --once       # executa uma vez e sai
"""

import argparse
import logging
import sys
import time

from .backfiller import run_backfill
from .chain_fetcher import fetch_chain
from .config import PAIRS, SYNC_INTERVAL_MIN
from .connector import disconnect, get_ib
from .pusher import push_signals
from .signal_engine import generate_signals
from .tech_analysis import fetch_tech_indicators

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("signals_agent")


def run_once(dry_run: bool = False) -> int:
    """Executa um ciclo completo: conecta → para cada par busca, calcula e envia."""
    ib = get_ib()
    total_enviados = 0
    falhas = 0

    for pair in PAIRS:
        symbol   = pair["symbol"]
        par      = pair["par"]
        exchange = pair.get("exchange", "CME")
        invert   = pair.get("invert_spot", False)
        logger.info("Processando %s (%s)…", par, symbol)

        try:
            chain = fetch_chain(ib, symbol, par, exchange=exchange, invert_spot=invert)
        except Exception as e:
            logger.error("[%s] Erro ao buscar cadeia: %s", symbol, e)
            falhas += 1
            continue

        if chain is None:
            continue

        try:
            tech = fetch_tech_indicators(ib, symbol, exchange)
        except Exception as e:
            logger.warning("[%s] Análise técnica falhou, usando padrão: %s", symbol, e)
            from .tech_analysis import TechIndicators
            tech = TechIndicators()

        try:
            signals = generate_signals(chain, tech)
        except Exception as e:
            logger.error("[%s] Erro ao gerar sinais: %s", symbol, e)
            falhas += 1
            continue

        if not signals:
            continue

        logger.info("[%s] Enviando %d sinais…", par, len(signals))
        ok = push_signals(signals, dry_run=dry_run)
        if ok:
            total_enviados += len(signals)
        else:
            falhas += 1

    logger.info("Ciclo concluído: %d sinais enviados, %d falhas.", total_enviados, falhas)
    return 0 if falhas == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Agente de sinais Forex IBKR")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcula sinais mas não envia ao Railway")
    parser.add_argument("--once", action="store_true",
                        help="Executa um ciclo e encerra")
    parser.add_argument("--backfill", action="store_true",
                        help="Importa 30 dias de IV histórica para popular o IV Rank imediatamente")
    args = parser.parse_args()

    try:
        if args.backfill:
            logger.info("Modo backfill: importando 30 dias de IV histórica…")
            run_backfill(dry_run=args.dry_run)
            sys.exit(0)

        if args.once or args.dry_run:
            sys.exit(run_once(dry_run=args.dry_run))

        logger.info("Iniciando loop a cada %d minutos. Ctrl+C para parar.", SYNC_INTERVAL_MIN)
        while True:
            run_once()
            logger.info("Aguardando %d min até próximo ciclo…", SYNC_INTERVAL_MIN)
            time.sleep(SYNC_INTERVAL_MIN * 60)

    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário.")
    finally:
        disconnect()


if __name__ == "__main__":
    main()
