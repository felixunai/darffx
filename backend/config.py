from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:pass@localhost/darffx"
    SECRET_KEY: str = "troque-isso-em-producao"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 dias
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRODUCT_IMAGE_URL: str = ""  # URL pública da imagem do produto (JPEG/PNG)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "DarfFX <noreply@darffx.com.br>"
    FRONTEND_URL: str = "http://localhost:5173"
    # Gmail SMTP (alternativa gratuita sem domínio próprio)
    SMTP_USER: str = ""      # seu Gmail: felixunai@gmail.com
    SMTP_PASSWORD: str = ""  # senha de app gerada no Google
    # Brevo (ex-Sendinblue) — HTTP API, 300 emails/dia grátis
    BREVO_API_KEY: str = ""
    BREVO_FROM_EMAIL: str = ""  # ex: darffx.app@gmail.com (verificado no Brevo)

    # Cron jobs — protegidos por secret
    CRON_SECRET: str = ""  # definir no .env; chamadas sem o secret são rejeitadas

    # Preços em centavos (BRL)
    PRECO_ACESSO_CENTAVOS: int = 6990   # R$ 69,90 — acesso anual (expira 31/12 do ano vigente)

    class Config:
        env_file = ".env"

settings = Settings()
