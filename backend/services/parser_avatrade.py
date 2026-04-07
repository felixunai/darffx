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
# balance: > COL_AMT_MAX

TIPOS_VALIDOS = {"CLOSED", "DEPOSIT", "OPENED", "WITHDRAWAL"}

@dataclass
class Operacao:
    adj_no: str
    data: datetime
    tipo: str
    descricao: str
    valor_usd: float


# ── PARSE PRINCIPAL ────────────────────────────────────────────────────────

def parse_pdf_avatrade(arquivo: BinaryIO) -> list[Operacao]:
    """
    Recebe o arquivo PDF da AvaTrade (BinaryIO) e retorna lista de Operacao.
    Estratégia: rasteriza cada página com PyMuPDF e aplica OCR com Tesseract.
    """
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
            # rasteriza a 200 DPI para boa precisão de OCR
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
    """Extrai operações de uma página rasterizada via OCR."""
    data = pytesseract.image_to_data(
        img, lang="eng", output_type=pytesseract.Output.DICT
    )

    # agrupa palavras por linha (Y com tolerância de 8px)
    grupos = _agrupar_por_y(data, tolerancia=8)
    operacoes = []

    for grupo in grupos:
        op = _grupo_para_operacao(grupo)
        if op:
            operacoes.append(op)

    return operacoes


def _agrupar_por_y(data: dict, tolerancia: int = 8) -> list[list[dict]]:
    """Agrupa palavras do OCR por proximidade vertical."""
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
    """Classifica palavras de um grupo por coluna e monta Operacao."""
    cols: dict[str, list[str]] = defaultdict(list)

    for item in sorted(grupo, key=lambda w: w["x"]):
        col = _classificar_coluna(item["x"])
        cols[col].append(item["text"])

    adj  = " ".join(cols.get("adj",  []))
    tipo = " ".join(cols.get("tipo", [])).upper()

    # só processa linhas com adj_no numérico e tipo válido
    if not adj.strip().isdigit() or len(adj.strip()) < 7:
        return None
    if tipo not in TIPOS_VALIDOS:
        return None

    data_str  = " ".join(cols.get("data",  []))
    descricao = " ".join(cols.get("desc",  []))
    amt_str   = " ".join(cols.get("amount",  []))

    data  = _parse_data(data_str)
    if not data:
        return None

    valor = _parse_valor(amt_str)

    # Reclassifica DEPOSIT negativo ou com keyword "withdrawal" como WITHDRAWAL
    if tipo == "DEPOSIT":
        desc_lower = descricao.lower()
        if "withdrawal" in desc_lower or "withdraw" in desc_lower:
            tipo = "WITHDRAWAL"
        elif valor < 0:
            tipo = "WITHDRAWAL"

    return Operacao(
        adj_no=adj.strip(),
        data=data,
        tipo=tipo,
        descricao=descricao,
        valor_usd=valor,
    )


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
    O OCR às vezes confunde '$' com 'S' → normaliza.
    """
    if not texto:
        return 0.0
    t = texto.strip()
    negativo = t.startswith("-")
    # remove prefixos US$, USS, US $, S$, etc.
    t = re.sub(r"-?\s*[Uu][Ss]?[Ss$]?\s*\$?\s*", "", t).strip()
    if not t:
        return 0.0

    if "," in t and "." in t:
        last_comma = t.rfind(",")
        last_dot   = t.rfind(".")
        if last_dot > last_comma:
            # formato US: 1,234.56 → vírgula é milhar, remove-a
            t = t.replace(",", "")
        else:
            # formato BR: 1.234,56 → ponto é milhar, vírgula vira decimal
            t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        parts = t.split(",")
        # vírgula de milhar US: exatamente 3 dígitos após a vírgula → 1,234 → 1234
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            t = t.replace(",", "")
        else:
            # vírgula decimal: 1,50 → 1.50
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
