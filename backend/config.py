from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:pass@localhost/darffx"
    SECRET_KEY: str = "troque-isso-em-producao"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 dias
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    RESEND_API_KEY: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    # Preços em centavos (BRL)
    PRECO_RELATORIO_CENTAVOS: int = 6900   # R$ 69,00
    PRECO_ANUAL_CENTAVOS: int = 4900       # R$ 49,00

    class Config:
        env_file = ".env"

settings = Settings()
