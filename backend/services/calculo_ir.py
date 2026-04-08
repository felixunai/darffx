"""
Serviço de cálculo de IR para Forex — Lei 14.754/2023 (vigente desde jan/2024).

Fórmula mensal (base para apuração anual):
  Lucro Líquido = Σ(ganhos) − Σ(perdas) − custos operacionais
  * AvaTrade não cobra taxas separadas — custo já embutido nos prêmios.

Regras:
- Apuração ANUAL (não mensal)
- Alíquota FIXA de 15% sobre o lucro líquido anual (Art. 2º Lei 14.754/2023)
  (Alíquotas progressivas se aplicam somente a offshores/controladas — não
   a contas diretas de corretora como AvaTrade)
- Sem isenção de R$ 20.000
- Compensação de prejuízos de meses anteriores dentro do mesmo ano-calendário
- PTAX: cotação de venda do dólar do último dia útil do mês de cada operação
- Declaração como "Aplicações financeiras no exterior"
- Vencimento: último dia útil de maio do ano seguinte (prazo IRPF)
"""
import re
import asyncio
import httpx
from datetime import date, timedelta
from calendar import monthrange
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict

ALIQUOTA_FIXA = 0.15  # 15% flat — Lei 14.754/2023


# ── DATACLASSES ──────────────────────────────────────────────────────────────

@dataclass
class ResultadoMensal:
    """Breakdown mensal para referência (não gera tributo próprio).

    Fórmula:
      ganho_usd = ganhos_usd − perdas_usd − custos_usd
    """
    mes: int
    ano: int
    # Componentes da fórmula
    ganhos_usd: float          # Σ operações positivas (realizadas)
    perdas_usd: float          # Σ operações negativas em valor absoluto
    custos_usd: float          # Taxas/corretagem (0 para AvaTrade)
    ganho_usd: float           # Resultado líquido = ganhos − perdas − custos
    ptax: float
    ganho_brl: float
    carry_fwd_brl: float
    base_tributavel_brl: float
    aliquota: float
    imposto_brl: float
    tem_day_trade: bool
    operacoes_count: int
    depositos_usd: float
    saques_usd: float
    vencimento_darf: Optional[date]


@dataclass
class ResultadoAnual:
    """Resultado anual consolidado — base real de tributação (Lei 14.754/2023)."""
    ano: int
    # P&L de trading
    lucro_usd: float
    lucro_brl: float
    # Compensação
    prejuizo_anterior_brl: float
    base_tributavel_brl: float
    # Imposto
    aliquota: float
    imposto_brl: float
    # Fluxos (para declaração como Aplicações Financeiras no Exterior)
    depositos_usd: float
    saques_usd: float
    # Metadados
    operacoes_count: int
    vencimento_darf: date
    breakdown_mensal: list = field(default_factory=list)


# ── PTAX ─────────────────────────────────────────────────────────────────────

async def buscar_ptax(mes: int, ano: int) -> Optional[float]:
    """PTAX de fechamento do último dia útil do mês (cria cliente próprio)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        return await _buscar_ptax_mes(client, mes, ano)


async def buscar_ptax_paralelo(
    meses_anos: list[tuple[int, int]]
) -> dict[tuple[int, int], float]:
    """Busca PTAX de vários meses em paralelo com um único cliente HTTP.
    Retorna dict {(mes, ano): ptax}. Muito mais rápido que chamadas sequenciais."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        tasks = [_buscar_ptax_mes(client, mes, ano) for mes, ano in meses_anos]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        (mes, ano): (float(r) if isinstance(r, float) else 0.0)
        for (mes, ano), r in zip(meses_anos, results)
    }


async def _buscar_ptax_mes(client: httpx.AsyncClient, mes: int, ano: int) -> Optional[float]:
    """Busca PTAX do último dia útil do mês usando cliente existente."""
    ultimo_dia = date(ano, mes, monthrange(ano, mes)[1])
    tentativas = 0
    delta = 0
    while tentativas < 7:
        dia = ultimo_dia - timedelta(days=delta)
        delta += 1
        if dia.weekday() >= 5:
            continue
        tentativas += 1
        ptax = await _buscar_ptax_dia(client, dia)
        if ptax:
            return ptax
    return None


async def buscar_ptax_por_data(data_op: date) -> Optional[float]:
    """PTAX de um dia específico (para depósitos/saques)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        for delta in range(0, 5):
            dia = data_op - timedelta(days=delta)
            if dia.weekday() >= 5:
                continue
            ptax = await _buscar_ptax_dia(client, dia)
            if ptax:
                return ptax
    return None


async def _buscar_ptax_dia(client: httpx.AsyncClient, dia: date) -> Optional[float]:
    data_str = dia.strftime("%m-%d-%Y")
    url = (
        "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        f"CotacaoDolarDia(dataCotacao=@dataCotacao)"
        f"?@dataCotacao='{data_str}'&$format=json&$select=cotacaoVenda"
    )
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            valores = resp.json().get("value", [])
            if valores:
                return float(valores[0]["cotacaoVenda"])
    except (httpx.RequestError, KeyError, ValueError):
        pass
    return None


# ── CÁLCULO MENSAL (breakdown / detalhe) ─────────────────────────────────────

def calcular_ir_mensal(
    operacoes: list,
    ptax: float,
    mes: int,
    ano: int,
    carry_fwd_brl: float = 0.0,
    custos_usd: float = 0.0,
) -> ResultadoMensal:
    """
    Breakdown mensal para exibição de detalhe.

    Fórmula (Lei 14.754/2023):
      ganho_usd = Σ(ganhos) − Σ(perdas) − custos_usd
      base_brl  = max(0, ganho_brl − prejuízo_acumulado_no_ano)
      imposto   = base_brl × 15%   → lançado no ajuste anual do IRPF

    O imposto aqui é referência proporcional — a tributação real é anual.
    """
    ops_mes = [
        op for op in operacoes
        if op.data.month == mes and op.data.year == ano
        and op.tipo in ("CLOSED", "OPENED")
    ]

    # Componentes da fórmula: separa ganhos e perdas
    ganhos_usd = round(sum(op.valor_usd for op in ops_mes if op.valor_usd > 0), 2)
    perdas_usd = round(sum(abs(op.valor_usd) for op in ops_mes if op.valor_usd < 0), 2)
    custos_usd = round(max(0.0, custos_usd), 2)
    ganho_usd  = round(ganhos_usd - perdas_usd - custos_usd, 2)

    depositos_usd = round(sum(
        op.valor_usd for op in operacoes
        if op.data.month == mes and op.data.year == ano
        and op.tipo == "DEPOSIT" and op.valor_usd > 0
    ), 2)
    saques_usd = round(sum(
        abs(op.valor_usd) for op in operacoes
        if op.data.month == mes and op.data.year == ano
        and (
            op.tipo == "WITHDRAWAL"
            or (op.tipo == "DEPOSIT" and op.valor_usd < 0)
        )
    ), 2)

    tem_day_trade = _detectar_day_trade(ops_mes)
    ganho_brl = round(ganho_usd * ptax, 2)

    # Compensação de prejuízo acumulado no ano (meses anteriores do mesmo ano)
    if ganho_brl > 0 and carry_fwd_brl > 0:
        base = round(max(0.0, ganho_brl - carry_fwd_brl), 2)
    elif ganho_brl > 0:
        base = ganho_brl
    else:
        base = 0.0

    return ResultadoMensal(
        mes=mes, ano=ano,
        ganhos_usd=ganhos_usd,
        perdas_usd=perdas_usd,
        custos_usd=custos_usd,
        ganho_usd=ganho_usd,
        ptax=ptax,
        ganho_brl=ganho_brl,
        carry_fwd_brl=round(carry_fwd_brl, 2),
        base_tributavel_brl=base,
        aliquota=ALIQUOTA_FIXA,
        imposto_brl=round(base * ALIQUOTA_FIXA, 2),
        tem_day_trade=tem_day_trade,
        operacoes_count=len([o for o in ops_mes if o.tipo == "CLOSED"]),
        depositos_usd=depositos_usd,
        saques_usd=saques_usd,
        vencimento_darf=_vencimento_darf_mensal(mes, ano),
    )


# ── CÁLCULO ANUAL (Lei 14.754/2023) ──────────────────────────────────────────

def calcular_ir_anual(
    meses: list[ResultadoMensal],
    ano: int,
    prejuizo_anterior_brl: float = 0.0,
) -> ResultadoAnual:
    """
    Consolida os meses do ano e calcula o imposto anual.
    Alíquota fixa 15% — sem isenção, sem tabela progressiva.
    Compensação de prejuízos de anos anteriores permitida.
    """
    lucro_usd = round(sum(m.ganho_usd for m in meses), 2)
    lucro_brl = round(sum(m.ganho_brl for m in meses), 2)
    depositos_usd = round(sum(m.depositos_usd for m in meses), 2)
    saques_usd    = round(sum(m.saques_usd for m in meses), 2)
    ops_count     = sum(m.operacoes_count for m in meses)

    # Compensação de prejuízo
    prejuizo_anterior_brl = round(max(0.0, prejuizo_anterior_brl), 2)
    if lucro_brl > 0 and prejuizo_anterior_brl > 0:
        base = round(max(0.0, lucro_brl - prejuizo_anterior_brl), 2)
    elif lucro_brl > 0:
        base = lucro_brl
    else:
        base = 0.0

    imposto = round(base * ALIQUOTA_FIXA, 2)

    return ResultadoAnual(
        ano=ano,
        lucro_usd=lucro_usd,
        lucro_brl=lucro_brl,
        prejuizo_anterior_brl=prejuizo_anterior_brl,
        base_tributavel_brl=base,
        aliquota=ALIQUOTA_FIXA,
        imposto_brl=imposto,
        depositos_usd=depositos_usd,
        saques_usd=saques_usd,
        operacoes_count=ops_count,
        vencimento_darf=_vencimento_darf_anual(ano),
        breakdown_mensal=meses,
    )


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _vencimento_darf_anual(ano: int) -> date:
    """Último dia útil de maio do ano seguinte (prazo IRPF — Lei 14.754/2023)."""
    ultimo_maio = date(ano + 1, 5, 31)
    while ultimo_maio.weekday() >= 5:
        ultimo_maio -= timedelta(days=1)
    return ultimo_maio


def _vencimento_darf_mensal(mes: int, ano: int) -> date:
    """Último dia útil do mês seguinte (mantido para compatibilidade de exibição)."""
    if mes == 12:
        prox_mes, prox_ano = 1, ano + 1
    else:
        prox_mes, prox_ano = mes + 1, ano
    ultimo = date(prox_ano, prox_mes, monthrange(prox_ano, prox_mes)[1])
    while ultimo.weekday() >= 5:
        ultimo -= timedelta(days=1)
    return ultimo


def _detectar_day_trade(operacoes: list) -> bool:
    """
    Day trade: mesmo número de ordem com OPENED e CLOSED no mesmo dia.
    Evita falsos positivos — AvaTrade usa números distintos para abertura/fechamento.
    """
    por_ordem_dia: dict = defaultdict(set)
    for op in operacoes:
        m = re.search(r'#(\d+)', op.descricao)
        if not m:
            continue
        chave = (m.group(1), op.data.date())
        por_ordem_dia[chave].add(op.tipo)

    return any(
        "OPENED" in tipos and "CLOSED" in tipos
        for tipos in por_ordem_dia.values()
    )


def nome_mes(mes: int) -> str:
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    return meses[mes - 1]
