"""
Parser do extrato PDF da AvaTrade (AvaOptions / MT4).

O PDF é gerado pelo "Print to PDF" do Windows — não contém texto extraível.
Usamos OCR (pytesseract) com classificação por posição X para reconstruir
as colunas corretamente.

Colunas do CASH LEDGER (200 DPI, A4 ≈ 1654px):
  adj_no   : x < 180
  data     : 180–450
  tipo     : 450–600
  descricao: 600–1100
  amount   : 1100–1370
  balance  : 1370+

Abordagem de parsing por seção:
  1. CASH LEDGER    → somente DEPOSIT e WITHDRAWAL
                      (adj_no de 8 dígitos começando com '2', ex: 20832319)
  2. PURCHASE AND SALES → trades REALIZADOS via linhas "TOTAL" (Net P/S)
                          A data de fechamento do leg CLOSE é usada para
                          atribuição mensal.

Seções ignoradas (evita double-counting):
  - TRADE LEDGER  (mesmos valores do Cash Ledger, adj_nos diferentes)
  - CURRENT STATUS (posições ainda abertas — não realizadas)
"""
import re
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor
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

# ── LARGURAS DE COLUNA (Cash Ledger, 200 DPI, A4 ≈ 1654px) ──────────────────
COL_ADJ_MAX  = 180
COL_DATA_MAX = 450
COL_TIPO_MAX = 600
COL_DESC_MAX = 1100
COL_AMT_MAX  = 1370

# ── SEÇÕES DO EXTRATO ─────────────────────────────────────────────────────────
_SEC_CASH   = "CASH_LEDGER"
_SEC_TRADE  = "TRADE_LEDGER"
_SEC_PS     = "PURCHASE_SALES"
_SEC_STATUS = "CURRENT_STATUS"

# Fuzzy map: prefixo OCR → tipo normalizado
_TIPO_PREFIXOS = {
    "CLOS": "CLOSED",
    "OPEN": "OPENED",
    "DEPO": "DEPOSIT",
    "WITH": "WITHDRAWAL",
    "WDRA": "WITHDRAWAL",
    "WDRL": "WITHDRAWAL",
}

_WITHDRAWAL_KEYWORDS = (
    "withdrawal", "withdraw", "wdl", "wth", ":wdr",
    "saqu", "retirad", "payout", "wire out",
)

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


# ── OCR WORKER (executa em thread paralela) ───────────────────────────────────

def _ocr_arquivo(path: str) -> list[list[dict]]:
    """Faz OCR de um arquivo de imagem e retorna grupos por linha Y."""
    img  = Image.open(path)
    data = pytesseract.image_to_data(img, lang="eng", output_type=pytesseract.Output.DICT)
    return _agrupar_por_y(data, tolerancia=8)


# ── PARSE PRINCIPAL ────────────────────────────────────────────────────────────

def parse_pdf_avatrade(arquivo: BinaryIO) -> list[Operacao]:
    if not OCR_DISPONIVEL:
        raise RuntimeError(
            "Dependências de OCR não instaladas. "
            "Execute: pip install pytesseract pillow pymupdf"
        )

    conteudo = arquivo.read()
    todos_grupos: list[list[dict]] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        doc = fitz.open(stream=conteudo, filetype="pdf")

        # Passo 1: renderiza todas as páginas para JPEG (rápido, sequencial)
        page_paths: list[str] = []
        for num_pag in range(len(doc)):
            pagina = doc[num_pag]
            mat  = fitz.Matrix(200/72, 200/72)
            pix  = pagina.get_pixmap(matrix=mat)
            path = os.path.join(tmpdir, f"pag_{num_pag:03d}.jpg")
            pix.save(path)
            page_paths.append(path)

        # Passo 2: OCR em paralelo (pytesseract usa subprocess → libera GIL)
        workers = min(4, len(page_paths))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            resultados = list(executor.map(_ocr_arquivo, page_paths))

        for grupos in resultados:
            todos_grupos.extend(grupos)

    operacoes = _parse_com_secoes(todos_grupos)

    # Remove duplicatas por adj_no
    vistos: set[str] = set()
    unicos: list[Operacao] = []
    for op in operacoes:
        if op.adj_no not in vistos:
            vistos.add(op.adj_no)
            unicos.append(op)

    return unicos


# ── PARSING POR SEÇÃO ─────────────────────────────────────────────────────────

def _parse_com_secoes(todos_grupos: list[list[dict]]) -> list[Operacao]:
    """
    Processa grupos OCR de todas as páginas com rastreamento de seção.

    Se o PDF contém seção Purchase & Sales (AvaOptions):
      - Cash Ledger  → DEPOSIT e WITHDRAWAL
      - Purchase & Sales → trades realizados via linhas TOTAL (Net P/S)

    Se o PDF NÃO contém seção Purchase & Sales (MT4 / formato antigo):
      - Cash Ledger  → CLOSED, OPENED, DEPOSIT e WITHDRAWAL (comportamento legado)

    O estado da seção P&S é mantido entre páginas para suportar pares que
    cruzam quebras de página.
    """
    depositos_saques: list[Operacao] = []
    cash_ledger_trades: list[Operacao] = []  # fallback para PDFs sem P&S
    ps_operacoes: list[Operacao] = []

    secao_atual = _SEC_CASH
    ps_secao_encontrada = False

    # Estado da seção P&S (preservado entre páginas)
    ps_data_close:  datetime | None = None
    ps_close_order: str | None      = None
    ps_contador      = 0
    ps_total_parcial = False   # True quando TOTAL splitado aguarda valor na prox. linha
    ps_sinal_total   = 1       # sinal do TOTAL splitado: +1 ou -1

    for grupo in todos_grupos:
        # Detecta transição de seção
        nova_secao = _detectar_secao(grupo)
        if nova_secao is not None:
            secao_atual = nova_secao
            if nova_secao == _SEC_PS:
                ps_secao_encontrada = True
            else:
                ps_data_close  = None
                ps_close_order = None
            continue

        # ── CASH LEDGER ───────────────────────────────────────────────────────
        if secao_atual == _SEC_CASH:
            op = _grupo_para_operacao(grupo)
            if not op:
                continue
            if op.tipo in ("DEPOSIT", "WITHDRAWAL"):
                depositos_saques.append(op)
            elif op.tipo in ("CLOSED", "OPENED"):
                # Guardamos para usar como fallback se não houver seção P&S
                cash_ledger_trades.append(op)

        # ── PURCHASE & SALES: extrai trades realizados ────────────────────────
        elif secao_atual == _SEC_PS:
            linha_txt = " ".join(w["text"] for w in sorted(grupo, key=lambda w: w["x"]))
            print(f"[PS] {linha_txt[:120]}", flush=True)

            if _e_linha_close_ps(grupo):
                data  = _extrair_data_ps(grupo)
                order = _extrair_order_ps(grupo)
                print(f"[PS-CLOSE] order={order} date={data}", flush=True)
                if data:
                    ps_data_close  = data
                if order:
                    ps_close_order = order
                ps_sinal_total   = 1   # reset sinal ao ver nova CLOSE line
                ps_total_parcial = False

            elif _e_linha_total_ps(grupo):
                net_pnl = _extrair_net_pnl(grupo)
                # Verifica sinal na linha ("TOTAL -US$" sem dígito)
                if net_pnl == 0.0:
                    linha_up = linha_txt.upper()
                    ps_sinal_total   = -1 if "-" in linha_up else 1
                    ps_total_parcial = True   # valor vem na próxima linha OCR
                    print(f"[PS-TOTAL-SPLIT] aguardando valor...", flush=True)
                else:
                    ps_total_parcial = False
                    _registrar_ps(ps_data_close, ps_close_order, net_pnl,
                                  ps_contador, ps_operacoes)
                    ps_contador   += 1
                    ps_data_close  = None
                    ps_close_order = None

            elif ps_total_parcial:
                # Linha de continuação de um TOTAL splitado ("73,90")
                v = _parse_valor(linha_txt)
                if v != 0.0:
                    net_pnl = ps_sinal_total * abs(v)
                    print(f"[PS-TOTAL-CONT] pnl={net_pnl} date={ps_data_close} order={ps_close_order}", flush=True)
                    _registrar_ps(ps_data_close, ps_close_order, net_pnl,
                                  ps_contador, ps_operacoes)
                    ps_contador      += 1
                    ps_data_close     = None
                    ps_close_order    = None
                ps_total_parcial = False

    # Decide qual fonte de trades usar
    if ps_secao_encontrada and ps_operacoes:
        # AvaOptions com P&S: usa P&S (P&L realizado preciso) + depósitos/saques
        return depositos_saques + ps_operacoes
    else:
        # MT4 / formato sem P&S: usa Cash Ledger completo (comportamento legado)
        return depositos_saques + cash_ledger_trades


# ── DETECÇÃO DE SEÇÃO ─────────────────────────────────────────────────────────

def _detectar_secao(grupo: list[dict]) -> str | None:
    """
    Retorna o nome da seção se o grupo for um cabeçalho de seção do extrato.
    Usa matching substring (tolerante a OCR) para cada palavra-chave.
    """
    linha = " ".join(w["text"].upper() for w in grupo)

    # "CASH LEDGER" — início da seção de fluxo de caixa
    if "CASH" in linha and "LEDGER" in linha:
        return _SEC_CASH

    # "TRADE LEDGER" — começa aqui, paramos de parsear OPENED/CLOSED
    if "TRADE" in linha and "LEDGER" in linha:
        return _SEC_TRADE

    # "PURCHASE AND SALES" (ou variações OCR)
    if "PURCHASE" in linha and "SALES" in linha:
        return _SEC_PS

    # "CURRENT STATUS" ou "CURRENT OPEN POSITIONS"
    if "CURRENT" in linha and ("STATUS" in linha or "POSITIONS" in linha):
        return _SEC_STATUS

    return None


# ── HELPERS DA SEÇÃO PURCHASE & SALES ────────────────────────────────────────

def _e_linha_close_ps(grupo: list[dict]) -> bool:
    """
    True se o grupo é uma linha de fechamento na seção P&S.
    Só verifica 'CLOS' em qualquer posição — sem dependência de x ou data,
    pois cabeçalhos nunca contêm 'CLOS'.
    """
    linha = " ".join(w["text"].upper() for w in grupo)
    return "CLOS" in linha


def _e_linha_total_ps(grupo: list[dict]) -> bool:
    """
    True se o grupo é uma linha TOTAL da seção P&S (com ou sem valor).
    'Total' deve ser a primeira ou segunda palavra da linha (menor x).
    Inclui TOTAL splitadas como 'TOTAL -US$' (sem dígito) para capturar
    linhas cujo valor numérico ficou na próxima linha OCR.
    """
    if not grupo:
        return False
    palavras_ord = sorted(grupo, key=lambda w: w["x"])
    primeiras = " ".join(w["text"].upper() for w in palavras_ord[:2])
    return "TOTAL" in primeiras


def _registrar_ps(ps_data_close, ps_close_order, net_pnl, ps_contador, ps_operacoes):
    """Cria e adiciona uma Operacao de P&S se a data de fechamento for conhecida."""
    print(f"[PS-TOTAL] pnl={net_pnl} date={ps_data_close} order={ps_close_order}", flush=True)
    if ps_data_close is None:
        return
    adj_id = f"PS{ps_close_order}" if ps_close_order else f"PS{ps_contador + 1:08d}"
    ps_operacoes.append(Operacao(
        adj_no=adj_id,
        data=ps_data_close,
        tipo="CLOSED",
        descricao=f"Realizado #{ps_close_order or ps_contador + 1}",
        valor_usd=net_pnl,
    ))


def _extrair_data_ps(grupo: list[dict]) -> datetime | None:
    """
    Extrai a data de fechamento de uma linha CLOSE na seção P&S.
    Tenta com timestamp completo; se a hora estiver na próxima linha OCR,
    aceita apenas a data (Mês DD YYYY) e usa 00:00 como hora.
    """
    linha = " ".join(w["text"] for w in sorted(grupo, key=lambda w: w["x"]))
    # Padrão completo: "Jan 15 2026 9:50PM"
    m = re.search(
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        r'\s+\d{1,2}\s+\d{4}\s+\d{1,2}:\d{2}(?:AM|PM)',
        linha, re.IGNORECASE,
    )
    if m:
        return _parse_data(m.group(0))
    # Fallback: apenas data (hora na próxima linha OCR)
    m = re.search(
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        r'\s+(\d{1,2})\s+(20\d\d)',
        linha, re.IGNORECASE,
    )
    if m:
        try:
            mes = datetime.strptime(m.group(1)[:3].capitalize(), '%b').month
            return datetime(int(m.group(3)), mes, int(m.group(2)))
        except Exception:
            pass
    return None


def _extrair_order_ps(grupo: list[dict]) -> str | None:
    """
    Extrai o número da ordem (6–8 dígitos) da coluna Order na seção P&S.
    O número da ordem é o primeiro bloco numérico de 6–8 dígitos na linha.
    """
    palavras = sorted(grupo, key=lambda w: w["x"])
    for w in palavras[:4]:   # as 4 primeiras palavras da esquerda
        for bloco in re.findall(r'\d+', w["text"]):
            if 6 <= len(bloco) <= 8:
                return bloco
    return None


def _extrair_net_pnl(grupo: list[dict]) -> float:
    """
    Extrai o Net P/S da linha TOTAL — o ÚLTIMO valor monetário da linha.
    Itera os tokens da direita para a esquerda até encontrar um valor válido.
    """
    todos = sorted(grupo, key=lambda w: -w["x"])   # direita → esquerda
    # Tenta janelas crescentes de tokens da direita
    for n in range(1, min(8, len(todos) + 1)):
        txt = " ".join(w["text"] for w in todos[:n])
        val = _parse_valor(txt)
        if val != 0.0:
            return val
    return 0.0


# ── OCR DE UMA PÁGINA (mantido para compatibilidade) ─────────────────────────

def _ocr_pagina(img: "Image.Image") -> list[Operacao]:
    """Mantido para compatibilidade — o novo fluxo usa _parse_com_secoes."""
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


# ── AGRUPAMENTO OCR ───────────────────────────────────────────────────────────

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


# ── GRUPO → OPERAÇÃO (Cash Ledger) ────────────────────────────────────────────

def _grupo_para_operacao(grupo: list[dict]) -> Operacao | None:
    cols: dict[str, list[str]] = defaultdict(list)

    for item in sorted(grupo, key=lambda w: w["x"]):
        col = _classificar_coluna(item["x"])
        cols[col].append(item["text"])

    adj_raw  = " ".join(cols.get("adj",  []))
    tipo_raw = " ".join(cols.get("tipo", [])).upper().strip()

    # ── adj_no: extrai maior bloco numérico contínuo (tolerante a OCR) ────────
    adj_blocos = re.findall(r'\d+', adj_raw)
    adj = max(adj_blocos, key=len) if adj_blocos else ""

    # Cash Ledger da AvaTrade usa adj_no de 8 dígitos começando com '2'
    # (ex: 20832319, 21176843).  Trade Ledger usa números de ordem de 7 dígitos
    # (ex: 4073299).  Filtrar aqui evita double-counting dessas seções.
    if len(adj) != 8 or adj[0] != '2':
        return None

    # ── tipo: fuzzy match por prefixo ─────────────────────────────────────────
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

    # ── corrige tipo usando a descrição ───────────────────────────────────────
    tipo, valor = _corrigir_tipo_e_valor(tipo, descricao, valor)

    # Fallback para depósitos/saques com valor zero: o OCR colocou o valor na
    # coluna balance (x > COL_AMT_MAX). Percorre a linha ordenada por x e pega
    # o primeiro padrão "US$ xxx" encontrado (que é o valor da transação).
    if tipo in ("DEPOSIT", "WITHDRAWAL") and valor == 0.0:
        print(f"[DEP-ZERO] adj={adj} amt_raw={amt_str!r}", flush=True)
        palavras_ord = sorted(grupo, key=lambda w: w["x"])
        linha_ord = " ".join(w["text"] for w in palavras_ord)
        for m in re.finditer(r'(?:US\$?|USS)\s*\$?\s*([-]?\s*[\d][\d,\.]*)', linha_ord, re.IGNORECASE):
            v = _parse_valor(m.group(0))
            if v != 0.0:
                valor = abs(v) if tipo == "DEPOSIT" else -abs(v)
                print(f"[DEP-FIXED] adj={adj} valor={valor}", flush=True)
                break

    return Operacao(
        adj_no=adj,
        data=data,
        tipo=tipo,
        descricao=descricao,
        valor_usd=valor,
    )


# ── NORMALIZAÇÃO DE TIPO ──────────────────────────────────────────────────────

def _normalizar_tipo(tipo_raw: str) -> str | None:
    """Normaliza tipo OCR tolerando truncamentos e substituições de letras."""
    t = tipo_raw.upper().strip()
    if not t:
        return None

    if t in {"CLOSED", "OPENED", "DEPOSIT", "WITHDRAWAL"}:
        return t

    for prefixo, tipo_real in _TIPO_PREFIXOS.items():
        if t.startswith(prefixo):
            return tipo_real

    t_limpo = t.replace("0", "O").replace("1", "I").replace("5", "S")
    if t_limpo.startswith("CLOS"): return "CLOSED"
    if t_limpo.startswith("OPEN"): return "OPENED"
    if t_limpo.startswith("DEPO"): return "DEPOSIT"
    if t_limpo.startswith("WITH"): return "WITHDRAWAL"

    return None


def _corrigir_tipo_e_valor(tipo: str, descricao: str, valor: float):
    """Usa a descrição (campo longo → OCR mais preciso) para corrigir tipo."""
    desc_lower = descricao.lower()

    if any(kw in desc_lower for kw in _WITHDRAWAL_KEYWORDS):
        return "WITHDRAWAL", -abs(valor)

    if tipo == "DEPOSIT" and valor < 0:
        return "WITHDRAWAL", valor

    if any(kw in desc_lower for kw in _DEPOSIT_KEYWORDS) and tipo == "DEPOSIT":
        return "DEPOSIT", abs(valor)

    return tipo, valor


# ── CLASSIFICAÇÃO DE COLUNA ───────────────────────────────────────────────────

def _classificar_coluna(x: int) -> str:
    if x < COL_ADJ_MAX:  return "adj"
    if x < COL_DATA_MAX: return "data"
    if x < COL_TIPO_MAX: return "tipo"
    if x < COL_DESC_MAX: return "desc"
    if x < COL_AMT_MAX:  return "amount"
    return "balance"


# ── HELPERS DE PARSING ────────────────────────────────────────────────────────

def _parse_valor(texto: str) -> float:
    """
    Converte 'US$ 1,234.56', 'USS 100.01', '-US$ 4.86', '- US$ 73,90' → float.
    O extrato da AvaTrade usa formato americano (ponto = decimal, vírgula = milhar).
    Tolerante a caracteres de ruído OCR no fim do valor (ex: '199,79B').
    """
    if not texto:
        return 0.0
    t = texto.strip()
    negativo = t.startswith("-")
    if negativo:
        t = t[1:].strip()  # remove leading '-' antes do regex (pode haver espaço após)
    t = re.sub(r"-?\s*[Uu][Ss]?[Ss$]?\s*\$?\s*", "", t).strip()
    if not t:
        return 0.0

    # Extrai o primeiro bloco numérico válido (ignora ruído OCR após o número)
    m = re.search(r'[\d,\.]+', t)
    if not m:
        return 0.0
    t = m.group(0).rstrip(",.")

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
