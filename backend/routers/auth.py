from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import uuid
import secrets
import logging

logger = logging.getLogger(__name__)

from ..models.database import User
from ..deps import get_db, get_current_user
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── ENVIO DE EMAIL (genérico) ─────────────────────────────────────────────────

def _enviar_email(to_email: str, assunto: str, html: str) -> None:
    """Tenta Resend → Brevo → Gmail SMTP em cascata."""

    if settings.RESEND_API_KEY:
        try:
            import resend
            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": settings.RESEND_FROM_EMAIL,
                "to": to_email,
                "subject": assunto,
                "html": html,
            })
            logger.info("E-mail enviado via Resend para %s", to_email)
            return
        except Exception as e:
            logger.error("Resend falhou (%s)", e)

    if settings.BREVO_API_KEY and settings.BREVO_FROM_EMAIL:
        try:
            import httpx
            resp = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": settings.BREVO_API_KEY, "Content-Type": "application/json"},
                json={
                    "sender": {"name": "DarfFX", "email": settings.BREVO_FROM_EMAIL},
                    "to": [{"email": to_email}],
                    "subject": assunto,
                    "htmlContent": html,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            logger.info("E-mail enviado via Brevo para %s", to_email)
            return
        except Exception as e:
            logger.error("Brevo falhou: %s", e)

    if settings.SMTP_USER and settings.SMTP_PASSWORD:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            msg = MIMEMultipart("alternative")
            msg["Subject"] = assunto
            msg["From"] = f"DarfFX <{settings.SMTP_USER}>"
            msg["To"] = to_email
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.sendmail(settings.SMTP_USER, to_email, msg.as_string())
            logger.info("E-mail enviado via Gmail SMTP para %s", to_email)
            return
        except Exception as e:
            logger.error("Gmail SMTP falhou: %s", e)

    logger.warning("Nenhum provedor configurado — e-mail não enviado para %s", to_email)


# ── TEMPLATES HTML ────────────────────────────────────────────────────────────

def _html_boas_vindas(nome: str | None) -> str:
    saudacao = f"Olá{', ' + nome if nome else ''}!"
    url = settings.FRONTEND_URL.rstrip("/")
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0e17;font-family:Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e17;padding:40px 16px">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#131929;border-radius:16px;border:1px solid rgba(255,255,255,0.08);overflow:hidden;max-width:520px;width:100%">

        <!-- HEADER -->
        <tr>
          <td style="background:linear-gradient(135deg,rgba(0,229,160,0.18) 0%,rgba(0,149,255,0.10) 100%);padding:32px 40px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.08)">
            <div style="font-size:30px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;font-family:Arial,sans-serif">
              Darf<span style="color:#00e5a0">FX</span>
            </div>
            <div style="color:rgba(255,255,255,0.45);font-size:12px;margin-top:6px;letter-spacing:0.5px">
              IR FOREX · LEI 14.754/2023
            </div>
          </td>
        </tr>

        <!-- BODY -->
        <tr>
          <td style="padding:32px 40px">
            <h2 style="color:#e8edf5;font-size:20px;margin:0 0 10px;font-family:Arial,sans-serif">
              {saudacao} Bem-vindo ao DarfFX!
            </h2>
            <p style="color:#8899aa;font-size:15px;line-height:1.75;margin:0 0 28px">
              Sua conta foi criada com sucesso. Agora você pode calcular seu imposto de renda sobre operações de Forex da AvaTrade de forma precisa, seguindo a <strong style="color:#e8edf5">Lei 14.754/2023</strong>.
            </p>

            <!-- STEPS -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;margin-bottom:28px">
              <tr>
                <td style="padding:20px 24px">
                  <div style="font-size:11px;font-weight:700;color:#00e5a0;letter-spacing:1px;margin-bottom:16px">COMO COMEÇAR EM 3 PASSOS</div>

                  <!-- Step 1 -->
                  <table cellpadding="0" cellspacing="0" style="margin-bottom:14px">
                    <tr>
                      <td style="vertical-align:top;padding-right:14px">
                        <div style="background:#00e5a0;color:#000;font-weight:700;font-size:12px;width:24px;height:24px;border-radius:50%;text-align:center;line-height:24px">1</div>
                      </td>
                      <td>
                        <div style="color:#e8edf5;font-size:14px;font-weight:600;margin-bottom:3px">Exporte o Account Statement</div>
                        <div style="color:#8899aa;font-size:13px;line-height:1.6">Acesse a AvaTrade → Relatórios → Account Statement, selecione o período e copie todo o conteúdo com <strong style="color:#e8edf5">Ctrl+A</strong> e <strong style="color:#e8edf5">Ctrl+C</strong></div>
                      </td>
                    </tr>
                  </table>

                  <!-- Step 2 -->
                  <table cellpadding="0" cellspacing="0" style="margin-bottom:14px">
                    <tr>
                      <td style="vertical-align:top;padding-right:14px">
                        <div style="background:#00e5a0;color:#000;font-weight:700;font-size:12px;width:24px;height:24px;border-radius:50%;text-align:center;line-height:24px">2</div>
                      </td>
                      <td>
                        <div style="color:#e8edf5;font-size:14px;font-weight:600;margin-bottom:3px">Cole no Excel ou Google Planilhas</div>
                        <div style="color:#8899aa;font-size:13px;line-height:1.6">Cole o conteúdo copiado em uma nova planilha e salve como <strong style="color:#e8edf5">CSV</strong> (Arquivo → Salvar como → CSV)</div>
                      </td>
                    </tr>
                  </table>

                  <!-- Step 3 -->
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="vertical-align:top;padding-right:14px">
                        <div style="background:#00e5a0;color:#000;font-weight:700;font-size:12px;width:24px;height:24px;border-radius:50%;text-align:center;line-height:24px">3</div>
                      </td>
                      <td>
                        <div style="color:#e8edf5;font-size:14px;font-weight:600;margin-bottom:3px">Faça o upload e veja seu IR</div>
                        <div style="color:#8899aa;font-size:13px;line-height:1.6">Envie o CSV no DarfFX. Em segundos calculamos seu imposto com a <strong style="color:#e8edf5">PTAX oficial do Banco Central</strong></div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>

            <!-- CTA -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px">
              <tr>
                <td align="center">
                  <a href="{url}/upload"
                     style="display:inline-block;background:#00e5a0;color:#000000;font-weight:700;font-size:15px;padding:14px 36px;border-radius:10px;text-decoration:none;letter-spacing:0.2px">
                    Fazer meu primeiro upload →
                  </a>
                </td>
              </tr>
            </table>

            <!-- INFO ROW -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px">
              <tr>
                <td width="33%" align="center" style="padding:0 8px">
                  <div style="font-size:11px;color:#8899aa;line-height:1.5">
                    <div style="font-size:18px;margin-bottom:4px">⚡</div>
                    Resultado em <strong style="color:#e8edf5">segundos</strong>
                  </div>
                </td>
                <td width="33%" align="center" style="padding:0 8px">
                  <div style="font-size:11px;color:#8899aa;line-height:1.5">
                    <div style="font-size:18px;margin-bottom:4px">🏦</div>
                    PTAX <strong style="color:#e8edf5">Banco Central</strong>
                  </div>
                </td>
                <td width="33%" align="center" style="padding:0 8px">
                  <div style="font-size:11px;color:#8899aa;line-height:1.5">
                    <div style="font-size:18px;margin-bottom:4px">⚖️</div>
                    <strong style="color:#e8edf5">Lei 14.754</strong>/2023
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:rgba(0,0,0,0.35);padding:18px 40px;border-top:1px solid rgba(255,255,255,0.06);text-align:center">
            <span style="color:rgba(255,255,255,0.3);font-size:11px;line-height:1.6">
              © {datetime.utcnow().year} DarfFX · Você recebe este e-mail por ter criado uma conta.<br>
              Dúvidas? Responda este e-mail.
            </span>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _html_recuperacao(nome: str | None, link: str) -> str:
    saudacao = f"Olá{', ' + nome if nome else ''}!"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0e17;font-family:Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e17;padding:40px 16px">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#131929;border-radius:16px;border:1px solid rgba(255,255,255,0.08);overflow:hidden;max-width:480px;width:100%">
        <tr>
          <td style="background:linear-gradient(135deg,rgba(0,229,160,0.15) 0%,rgba(0,149,255,0.08) 100%);padding:28px 40px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.08)">
            <div style="font-size:26px;font-weight:800;color:#fff">Darf<span style="color:#00e5a0">FX</span></div>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 40px">
            <h2 style="color:#e8edf5;font-size:18px;margin:0 0 12px">{saudacao}</h2>
            <p style="color:#8899aa;font-size:14px;line-height:1.75;margin:0 0 28px">
              Recebemos uma solicitação para redefinir sua senha. Clique no botão abaixo para criar uma nova senha.
            </p>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px">
              <tr><td align="center">
                <a href="{link}" style="display:inline-block;background:#00e5a0;color:#000;font-weight:700;font-size:14px;padding:13px 32px;border-radius:9px;text-decoration:none">
                  Redefinir senha →
                </a>
              </td></tr>
            </table>
            <p style="color:rgba(255,255,255,0.3);font-size:12px;text-align:center;line-height:1.6;margin:0">
              Este link expira em 2 horas. Se você não solicitou, ignore este e-mail.
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:rgba(0,0,0,0.3);padding:16px 40px;border-top:1px solid rgba(255,255,255,0.06);text-align:center">
            <span style="color:rgba(255,255,255,0.3);font-size:11px">© {datetime.utcnow().year} DarfFX</span>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── FUNÇÕES DE ENVIO ──────────────────────────────────────────────────────────

def _enviar_email_boas_vindas(to_email: str, nome: str | None) -> None:
    _enviar_email(to_email, "Bem-vindo ao DarfFX — veja como começar", _html_boas_vindas(nome))


def _enviar_email_recuperacao(to_email: str, nome: str | None, link: str) -> None:
    _enviar_email(to_email, "DarfFX — Recuperação de senha", _html_recuperacao(nome, link))


# ── MODELOS ───────────────────────────────────────────────────────────────────

class RegisterIn(BaseModel):
    email: EmailStr
    senha: str
    nome: str | None = None

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

def criar_token(user_id: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": exp}, settings.SECRET_KEY, settings.ALGORITHM)


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=data.email).first():
        raise HTTPException(400, "E-mail já cadastrado.")
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        nome=data.nome,
        hashed_password=pwd_ctx.hash(data.senha),
    )
    db.add(user)
    db.commit()
    # E-mail enviado em background — não bloqueia o cadastro
    background_tasks.add_task(_enviar_email_boas_vindas, user.email, user.nome)
    return {"access_token": criar_token(user.id)}


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=form.username).first()
    if not user or not pwd_ctx.verify(form.password, user.hashed_password):
        raise HTTPException(401, "E-mail ou senha incorretos.")
    return {"access_token": criar_token(user.id)}


class SolicitarResetIn(BaseModel):
    email: EmailStr

class ConfirmarResetIn(BaseModel):
    token: str
    nova_senha: str

@router.post("/recuperar-senha")
def solicitar_reset(data: SolicitarResetIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=data.email).first()
    if not user:
        return {"ok": True, "msg": "Se o e-mail existir, você receberá as instruções."}

    from ..models.database import ResetToken
    db.query(ResetToken).filter_by(user_id=user.id, used=False).update({"used": True})

    token = secrets.token_urlsafe(32)
    rt = ResetToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(hours=2),
    )
    db.add(rt)
    db.commit()

    link = f"{settings.FRONTEND_URL}/nova-senha?token={token}"
    background_tasks.add_task(_enviar_email_recuperacao, user.email, user.nome, link)
    return {"ok": True, "msg": "Se o e-mail existir, você receberá as instruções."}


@router.post("/nova-senha")
def confirmar_reset(data: ConfirmarResetIn, db: Session = Depends(get_db)):
    from ..models.database import ResetToken
    rt = db.query(ResetToken).filter_by(token=data.token, used=False).first()
    if not rt or rt.expires_at < datetime.utcnow():
        raise HTTPException(400, "Link inválido ou expirado.")
    if len(data.nova_senha) < 6:
        raise HTTPException(400, "A senha deve ter pelo menos 6 caracteres.")

    user = db.query(User).filter_by(id=rt.user_id).first()
    user.hashed_password = pwd_ctx.hash(data.nova_senha)
    rt.used = True
    db.commit()
    return {"ok": True, "msg": "Senha redefinida com sucesso!"}


@router.get("/me")
def me(usuario: User = Depends(get_current_user)):
    expirado = (
        usuario.plano_expiracao is not None
        and usuario.plano_expiracao < datetime.utcnow()
        and usuario.plano == "pago"
    )
    return {
        "id":              usuario.id,
        "email":           usuario.email,
        "nome":            usuario.nome,
        "plano":           usuario.plano,
        "plano_expiracao": usuario.plano_expiracao.isoformat() if usuario.plano_expiracao else None,
        "plano_expirado":  expirado,
        "is_admin":        usuario.email == "felixunai@gmail.com",
    }
