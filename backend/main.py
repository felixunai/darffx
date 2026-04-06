from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, apuracao
from .deps import init_db
from .config import settings

app = FastAPI(
    title="DarfFX API",
    description="Cálculo de IR para traders Forex brasileiros",
    version="1.0.0",
)

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

@app.get("/health")
def health():
    return {"status": "ok", "service": "DarfFX API"}
