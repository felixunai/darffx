"""
Parser do extrato CSV da AvaTrade.

Fluxo para o usuário:
  1. Abrir o relatório Account Statement na AvaTrade
  2. Selecionar todo o texto (Ctrl+A) e copiar (Ctrl+C)
  3. Colar em uma planilha (Excel ou Google Sheets) e salvar como CSV

Formato das colunas (após cabeçalho):
  0: Adj_No
  1: Trans. Date (GMT)  — "jan. 2 2026 15:00" ou "Feb 2 2026 1:17AM"
  2: Type               — CLOSED, OPENED, DEPOSIT, WITHDRAWAL, OVERNIGHT INTEREST CR.
  3: Description
  4: Amount             — formato BR: "-US$ 57,61", "US$ 3.255,21"
  5: Balance
"""
import csv
import re
import io
from datetime import datetime
from typing import BinaryIO

from .parser_avatrade import Operacao

_TIPOS_RELEVANTES = {"CLOSED", "OPENED", "DEPOSIT", "WITHDRAWAL"}

# Meses abreviados em português → inglês
_MESES_PT = {
    "jan": "Jan", "fev": "Feb", "mar": "Mar", "abr": "Apr",
    "mai": "May", "jun": "Jun", "jul": "Jul", "ago": "Aug",
    "set": "Sep", "out": "Oct", "nov": "Nov", "dez": "Dec",
}


def parse_csv_avatrade(arquivo: BinaryIO) -> list[Operacao]:
    """Lê um CSV exportado do extrato AvaTrade e retorna lista de Operacao."""
    conteudo = arquivo.read()

    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError("Não foi possível decodificar o arquivo CSV. Salve como UTF-8.")

    reader = csv.reader(io.StringIO(texto))
    operacoes: list[Operacao] = []
    vistos: set[str] = set()

    for row in reader:
        if len(row) < 5:
            continue

        adj_raw = row[0].strip()
        # Adj_No do Cash Ledger: 8 dígitos começando com '2' (ex: 20832319)
        if not re.fullmatch(r'2\d{7}', adj_raw):
            continue

        tipo_raw = row[2].strip().upper()
        if tipo_raw not in _TIPOS_RELEVANTES:
            continue

        data = _parse_data(row[1].strip())
        if not data:
            continue

        valor = _parse_valor(row[4].strip()) if len(row) > 4 else 0.0

        if tipo_raw == "WITHDRAWAL":
            valor = -abs(valor)
        elif tipo_raw == "DEPOSIT":
            valor = abs(valor)

        if adj_raw in vistos:
            continue
        vistos.add(adj_raw)

        operacoes.append(Operacao(
            adj_no=adj_raw,
            data=data,
            tipo=tipo_raw,
            descricao=row[3].strip() if len(row) > 3 else "",
            valor_usd=valor,
        ))

    return operacoes


def _parse_data(texto: str) -> datetime | None:
    """
    Converte datas do CSV AvaTrade em datetime.

    Formatos no mesmo arquivo:
      "jan. 2 2026 15:00"  — mês PT com ponto, 24h
      "Feb 2 2026 1:17AM"  — mês EN sem ponto, 12h AM/PM
    """
    t = texto.strip()
    if not t:
        return None

    # Normaliza mês português para inglês: "jan." → "Jan"
    t = re.sub(
        r'^([A-Za-záàâãéèêíóôõúç]+)\.?\s+',
        lambda m: (_MESES_PT.get(m.group(1).lower()[:3], m.group(1).capitalize()) + " "),
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r'\s+', ' ', t).strip()

    formatos = [
        "%b %d %Y %H:%M",      # "Jan 2 2026 15:00"
        "%b %d %Y %I:%M%p",    # "Feb 2 2026 1:17AM"
        "%b %d %Y %I:%M %p",
        "%b %d %Y %I:%M:%S%p",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    return None


def _parse_valor(texto: str) -> float:
    """
    Converte valores do CSV AvaTrade (formato BR: ponto=milhar, vírgula=decimal).

    "-US$ 57,61"   → -57.61
    "US$ 3.255,21" → 3255.21
    "US$ 0,00"     → 0.0
    """
    if not texto:
        return 0.0
    t = texto.strip()
    negativo = t.startswith("-")
    t = re.sub(r'^-?\s*[Uu][Ss]\$\s*', '', t).strip()
    if not t:
        return 0.0
    # Formato BR: remove milhar (ponto) e converte decimal (vírgula → ponto)
    t = t.replace(".", "").replace(",", ".")
    try:
        valor = float(t)
        return -valor if negativo else valor
    except ValueError:
        return 0.0
