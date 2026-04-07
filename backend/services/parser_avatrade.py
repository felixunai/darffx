"""
Parser do extrato PDF da AvaTrade (AvaOptions / MT4).

O PDF é gerado pelo "Print to PDF" do Windows — não contém texto extraível.
Usamos OCR (pytesseract) com classificação por posição X para reconstruir
as colunas do Cash Ledger corretamente.

Colunas detectadas (baseado em página 1654px de largura a 200 DPI):
  adj_no   : x < 180
  data     : 180–450
  tipo     : 450–600
  descricao: 600–1100
  amount   : 1100–1370
  balance  : 1370+
"""
import re
import tempfile
import os
from datetime import datetime
from typing import BinaryIO
from dataclasses import dataclass
from collections import defaultdict

try:
    import pytesseract
    from PIL import Image
    import fitz  # PyMuPDF
    OCR_DISPONIVEL = True
except ImportError:
    OCR_DISPONIVEL = False

# ── LARGURAS DE COLUNA (em pixels a 200 DPI, página A4 ≈ 1654px) ──────────
COL_ADJ_MAX  = 180
COL_DATA_MAX = 450
COL_TIPO_MAX = 600
COL_DESC_MAX = 1100
COL_AMT_MAX  = 1370

# Fuzzy map: prefixo OCR → tipo normalizado
_TIPO_PREFIXOS = {
    "CLOS": "CLOSED",
    "OPEN": "OPENED",
    "DEPO": "DEPOSIT",
    "WITH": "WITHDRAWAL",
    "WDRA": "WITHDRAWAL",
    "WDRL": "WITHDRAWAL",
}

# Palavras-chave que identificam saque na descrição (campo mais longo = OCR mais preciso)
_WITHDRAWAL_KEYWORDS = (
    "withdrawal", "withdraw", "wdl", "wth", ":wdr",
    "saqu", "retirad", "payout", "wire out",
)

# Palavras-chave que identificam depósito na descrição
_DEPOSIT_KEYWORDS = (
    ":deposit", "deposit:", "praxispay", "wire in", "funding",
)


@dataclass
class Operacao:
    adj_no: str
    data: datetime
    tipo: str
    descricao: str
    valor_usd: float


# ── PARSE PRINCIPAL ────────────────────────────────────────────────────────

def parse_pdf_avatrade(arquivo: BinaryIO) -> list[Operacao]:
    if not OCR_DISPONIVEL:
        raise RuntimeError(
            "Dependências de OCR não instaladas. "
            "Execute: pip install pytesseract pillow pymupdf"
        )

    conteudo = arquivo.read()
    operacoes: list[Operacao] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        doc = fitz.open(stream=conteudo, filetype="pdf")

        for num_pag in range(len(doc)):
            pagina = doc[num_pag]
            mat  = fitz.Matrix(200/72, 200/72)
            pix  = pagina.get_pixmap(matrix=mat)
            path = os.path.join(tmpdir, f"pag_{num_pag:03d}.jpg")
            pix.save(path)

            img = Image.open(path)
            ops = _ocr_pagina(img)
            operacoes.extend(ops)

    # remove duplicatas por adj_no
    vistos: set[str] = set()
    unicos: list[Operacao] = []
    for op in operacoes:
        if op.adj_no not in vistos:
            vistos.add(op.adj_no)
            unicos.append(op)

    return unicos


# ── OCR DE UMA PÁGINA ─────────────────────────────────────────────────────

def _ocr_pagina(img: "Image.Image") -> list[Operacao]:
    data = pytesseract.image_to_data(
        img, lang="eng", output_type=pytesseract.Output.DICT
    )
    grupos = _agrupar_por_y(data, tolerancia=8)
    operacoes = []
    for grupo in grupos:
        op = _grupo_para_operacao(grupo)
        if op:
            operacoes.append(op)
    return operacoes


def _agrupar_por_y(data: dict, tolerancia: int = 8) -> list[list[dict]]:
    palavras = []
    for i, word in enumerate(data["text"]):
        if word.strip() and int(data["conf"][i]) > 20:
            palavras.append({
                "x":    data["left"][i],
                "y":    data["top"][i],
                "text": word,
            })

    palavras.sort(key=lambda w: w["y"])

    grupos: list[list[dict]] = []
    for item in palavras:
        adicionado = False
        for g in grupos:
            if abs(g[0]["y"] - item["y"]) <= tolerancia:
                g.append(item)
                adicionado = True
                break
        if not adicionado:
            grupos.append([item])

    return grupos


def _grupo_para_operacao(grupo: list[dict]) -> Operacao | None:
    cols: dict[str, list[str]] = defaultdict(list)

    for item in sorted(grupo, key=lambda w: w["x"]):
        col = _classificar_coluna(item["x"])
        cols[col].append(item["text"])

    adj_raw  = " ".join(cols.get("adj",  []))
    tipo_raw = " ".join(cols.get("tipo", [])).upper().strip()

    # ── adj_no: extrai maior bloco numérico contínuo (tolerante a OCR) ─────
    adj_blocos = re.findall(r'\d+', adj_raw)
    adj = max(adj_blocos, key=len) if adj_blocos else ""
    if len(adj) < 5:          # precisa de pelo menos 5 dígitos
        return None

    # ── tipo: fuzzy match por prefixo ──────────────────────────────────────
    tipo = _normalizar_tipo(tipo_raw)
    if not tipo:
        return None

    data_str  = " ".join(cols.get("data",  []))
    descricao = " ".join(cols.get("desc",  []))
    amt_str   = " ".join(cols.get("amount", []))

    data = _parse_data(data_str)
    if not data:
        return None

    valor = _parse_valor(amt_str)

    # ── corrige tipo usando a descrição (campo mais longo → OCR mais preciso)
    tipo, valor = _corrigir_tipo_e_valor(tipo, descricao, valor)

    return Operacao(
        adj_no=adj,
        data=data,
        tipo=tipo,
        descricao=descricao,
        valor_usd=valor,
    )


def _normalizar_tipo(tipo_raw: str) -> str | None:
    """Normaliza tipo OCR tolerando truncamentos e substituições de letras."""
    t = tipo_raw.upper().strip()
    if not t:
        return None

    # Match exato
    if t in {"CLOSED", "OPENED", "DEPOSIT", "WITHDRAWAL"}:
        return t

    # Match por prefixo (ex.: "CLOS", "DEPO", "WITH")
    for prefixo, tipo_real in _TIPO_PREFIXOS.items():
        if t.startswith(prefixo):
            return tipo_real

    # Match com erros de OCR comuns (O→0, I→1, etc.)
    t_limpo = t.replace("0", "O").replace("1", "I").replace("5", "S")
    if t_limpo.startswith("CLOS"): return "CLOSED"
    if t_limpo.startswith("OPEN"): return "OPENED"
    if t_limpo.startswith("DEPO"): return "DEPOSIT"
    if t_limpo.startswith("WITH"): return "WITHDRAWAL"

    return None


def _corrigir_tipo_e_valor(tipo: str, descricao: str, valor: float):
    """
    Usa a descrição para corrigir tipo incorreto.
    A descrição é um campo maior → OCR mais preciso que o campo tipo (curto).
    """
    desc_lower = descricao.lower()

    # Saque: keyword na descrição, independente do tipo OCR
    if any(kw in desc_lower for kw in _WITHDRAWAL_KEYWORDS):
        # Se OCR perdeu o sinal negativo, força negativo
        valor_corrigido = -abs(valor)
        return "WITHDRAWAL", valor_corrigido

    # Se tipo é DEPOSIT mas valor é negativo → saque não identificado por keyword
    if tipo == "DEPOSIT" and valor < 0:
        return "WITHDRAWAL", valor

    # Depósito: keyword na descrição confirma
    if any(kw in desc_lower for kw in _DEPOSIT_KEYWORDS) and tipo == "DEPOSIT":
        return "DEPOSIT", abs(valor)   # garante positivo

    return tipo, valor


def _classificar_coluna(x: int) -> str:
    if x < COL_ADJ_MAX:  return "adj"
    if x < COL_DATA_MAX: return "data"
    if x < COL_TIPO_MAX: return "tipo"
    if x < COL_DESC_MAX: return "desc"
    if x < COL_AMT_MAX:  return "amount"
    return "balance"


# ── HELPERS DE PARSING ────────────────────────────────────────────────────

def _parse_valor(texto: str) -> float:
    """
    Converte 'US$ 1,234.56', 'USS 100.01', '-US$ 4.86' → float.
    O extrato da AvaTrade usa formato americano (ponto = decimal, vírgula = milhar).
    """
    if not texto:
        return 0.0
    t = texto.strip()
    negativo = t.startswith("-")
    t = re.sub(r"-?\s*[Uu][Ss]?[Ss$]?\s*\$?\s*", "", t).strip()
    if not t:
        return 0.0

    if "," in t and "." in t:
        last_comma = t.rfind(",")
        last_dot   = t.rfind(".")
        if last_dot > last_comma:
            t = t.replace(",", "")
        else:
            t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        parts = t.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            t = t.replace(",", "")
        else:
            t = t.replace(",", ".")

    try:
        valor = float(t)
        return -valor if negativo else valor
    except ValueError:
        return 0.0


def _parse_data(texto: str) -> datetime | None:
    """Converte 'Sep 2 2025 7:25PM' → datetime. Tolerante a espaços extras."""
    texto = re.sub(r"\s+", " ", texto).strip()
    formatos = [
        "%b %d %Y %I:%M%p",
        "%b %d %Y %I:%M %p",
        "%b %d %Y %I:%M:%S%p",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None
