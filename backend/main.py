from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .routers import auth, apuracao, admin, pagamento, cron
from .deps import init_db
from .config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title="DarfFX API",
    description="Cálculo de IR para traders Forex brasileiros",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

app.include_router(auth.router)
app.include_router(apuracao.router)
app.include_router(admin.router)
app.include_router(pagamento.router)
app.include_router(cron.router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "DarfFX API"}
