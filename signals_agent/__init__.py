# Python 3.10+ não cria event loop automaticamente — ib_insync/eventkit exige um.
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
