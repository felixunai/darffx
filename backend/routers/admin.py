"""
Router: /admin  (acesso restrito a felixunai@gmail.com)
- GET  /admin/stats           — resumo geral
- GET  /admin/users           — lista todos os usuários
- GET  /admin/users/{id}      — detalhe do usuário
- PATCH /admin/users/{id}/plano — altera plano + expiração
- PATCH /admin/users/{id}/ativo — ativa/desativa conta
- DELETE /admin/users/{id}    — remove usuário
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional

from ..models.database import User, Apuracao, ApuracaoAnual, PromoConfig
from ..deps import get_db, get_admin_user

router = APIRouter(prefix="/admin", tags=["admin"])

PLANOS_VALIDOS = {"free", "pago", "admin"}

class AlterarPlanoIn(BaseModel):
    plano: str
    dias: Optional[int] = None   # para mensal/anual: duração em dias (padrão 30 ou 365)

class AtivoIn(BaseModel):
    ativo: bool

class PromoIn(BaseModel):
    ativo: Optional[bool] = None
    preco_centavos: Optional[int] = None

# ── STATS ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def stats(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    total_users     = db.query(func.count(User.id)).scalar()
    total_apuracoes = db.query(func.count(Apuracao.id)).scalar()
    por_plano = (
        db.query(User.plano, func.count(User.id))
        .group_by(User.plano)
        .all()
    )
    return {
        "total_users": total_users,
        "total_apuracoes": total_apuracoes,
        "por_plano": {p: c for p, c in por_plano},
    }

# ── USERS ─────────────────────────────────────────────────────────────────────

@router.get("/users")
def listar_users(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_user_dict(u, db) for u in users]

@router.get("/users/{user_id}")
def detalhe_user(user_id: str, db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(404, "Usuário não encontrado.")
    return _user_dict(u, db, incluir_apuracoes=True)

@router.patch("/users/{user_id}/plano")
def alterar_plano(
    user_id: str,
    body: AlterarPlanoIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    if body.plano not in PLANOS_VALIDOS:
        raise HTTPException(400, f"Plano inválido. Use: {PLANOS_VALIDOS}")

    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(404, "Usuário não encontrado.")

    u.plano = body.plano

    if body.plano == "free":
        u.plano_expiracao = None
        # Revoga acesso: bloqueia todos os relatórios do usuário
        db.query(ApuracaoAnual).filter_by(user_id=u.id).update({"desbloqueado": False})
    elif body.plano == "admin":
        u.plano_expiracao = None
    elif body.plano == "pago":
        # Expiração: 31/12 do ano vigente (ou dias customizados)
        if body.dias:
            u.plano_expiracao = datetime.utcnow() + timedelta(days=body.dias)
        else:
            ano = datetime.utcnow().year
            u.plano_expiracao = datetime(ano, 12, 31, 23, 59, 59)

    db.commit()
    return _user_dict(u, db)

@router.patch("/users/{user_id}/ativo")
def alterar_ativo(
    user_id: str,
    body: AtivoIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(404, "Usuário não encontrado.")
    u.ativo = body.ativo
    db.commit()
    return _user_dict(u, db)

@router.patch("/apuracoes-anuais/{apuracao_id}/desbloquear")
def desbloquear_apuracao(
    apuracao_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """Admin pode desbloquear qualquer relatório sem pagamento."""
    from ..models.database import ApuracaoAnual
    a = db.query(ApuracaoAnual).filter_by(id=apuracao_id).first()
    if not a:
        raise HTTPException(404, "Apuração não encontrada.")
    a.desbloqueado = True
    db.commit()
    return {"ok": True, "ano": a.ano, "user_id": a.user_id}


@router.delete("/users/{user_id}")
def deletar_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    if user_id == admin.id:
        raise HTTPException(400, "Não é possível excluir o próprio usuário admin.")
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(404, "Usuário não encontrado.")
    db.delete(u)
    db.commit()
    return {"ok": True}

# ── PROMO CONFIG ──────────────────────────────────────────────────────────────

@router.get("/config/promo")
def get_promo(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    p = db.query(PromoConfig).filter_by(id=1).first()
    return _promo_dict(p)

@router.patch("/config/promo")
def set_promo(
    body: PromoIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    p = db.query(PromoConfig).filter_by(id=1).first()
    if body.ativo is not None:
        p.ativo = body.ativo
    if body.preco_centavos is not None:
        if body.preco_centavos < 100:
            raise HTTPException(400, "Preço mínimo: R$ 1,00 (100 centavos).")
        p.preco_centavos = body.preco_centavos
    db.commit()
    return _promo_dict(p)

def _promo_dict(p: PromoConfig) -> dict:
    return {
        "ativo": p.ativo,
        "preco_centavos": p.preco_centavos,
        "preco_brl": f"R$ {p.preco_centavos / 100:.2f}".replace(".", ","),
    }


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _user_dict(u: User, db: Session, incluir_apuracoes=False) -> dict:
    count = db.query(func.count(Apuracao.id)).filter_by(user_id=u.id).scalar()
    d = {
        "id": u.id,
        "email": u.email,
        "nome": u.nome,
        "plano": u.plano,
        "plano_expiracao": u.plano_expiracao.isoformat() if u.plano_expiracao else None,
        "ativo": u.ativo,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "apuracoes_count": count,
    }
    if incluir_apuracoes:
        aps = db.query(Apuracao).filter_by(user_id=u.id).order_by(Apuracao.ano, Apuracao.mes).all()
        d["apuracoes"] = [
            {
                "id": a.id, "mes": a.mes, "ano": a.ano,
                "ganho_usd": round(a.ganho_usd or 0, 2),
                "imposto_brl": round(a.imposto_brl or 0, 2),
                "darf_pago": a.darf_pago,
            }
            for a in aps
        ]
    return d
