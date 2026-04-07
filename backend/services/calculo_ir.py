"""
Serviço de cálculo de IR para Forex.
- Busca PTAX oficial do Banco Central do Brasil
- Calcula ganho/perda em BRL
- Aplica alíquota correta (15% swap/spot, 20% day trade)
- Regra vigente desde jan/2024: sem isenção, tudo tributado
- Carry Forward: perdas de meses anteriores reduzem base tributável
"""
import re
import httpx
from datetime import date, timedelta
from calendar import monthrange
from typing import Optional
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class ResultadoMensal:
    mes: int
    ano: int
    ganho_usd: float
    ptax: float
    ganho_brl: float
    carry_fwd_brl: float        # perdas acumuladas de meses anteriores
    base_tributavel_brl: float  # ganho_brl - carry_fwd_brl (base real do imposto)
    aliquota: float
    imposto_brl: float
    tem_day_trade: bool
    operacoes_count: int
    vencimento_darf: Optional[date]

ALIQUOTA_NORMAL    = 0.15   # 15% — operações normais
ALIQUOTA_DAY_TRADE = 0.20   # 20% — day trade

async def buscar_ptax(mes: int, ano: int) -> Optional[float]:
    """
    Busca a PTAX de fechamento do último dia útil do mês.
    Fonte: API oficial do Banco Central do Brasil.
    Retenta até 7 dias úteis anteriores caso não haja cotação.
    """
    ultimo_dia = date(ano, mes, monthrange(ano, mes)[1])

    async with httpx.AsyncClient(timeout=10.0) as client:
        tentativas = 0
        delta = 0
        while tentativas < 7:
            dia = ultimo_dia - timedelta(days=delta)
            delta += 1
            # pula fins de semana
            if dia.weekday() >= 5:
                continue
            tentativas += 1

            data_str = dia.strftime("%m-%d-%Y")
            url = (
                "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
                f"CotacaoDolarDia(dataCotacao=@dataCotacao)"
                f"?@dataCotacao='{data_str}'&$format=json&$select=cotacaoVenda"
            )

            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    dados = resp.json()
                    valores = dados.get("value", [])
                    if valores:
                        return float(valores[0]["cotacaoVenda"])
            except (httpx.RequestError, KeyError, ValueError):
                continue

    return None

def calcular_ir_mensal(
    operacoes: list,
    ptax: float,
    mes: int,
    ano: int,
    carry_fwd_brl: float = 0.0,
) -> ResultadoMensal:
    """
    Recebe lista de Operacao (OPENED + CLOSED), PTAX, mês/ano e carry forward.
    Retorna ResultadoMensal com todos os valores calculados.

    Regra 2024+:
    - Para AvaOptions: P&L = soma de OPENED (prêmios) + CLOSED (liquidação)
    - Carry Forward: perdas de meses anteriores reduzem a base tributável
    - Alíquota = 15% normal / 20% se houver day trade confirmado
    - Sem isenção
    """
    ops_mes = [
        op for op in operacoes
        if op.data.month == mes and op.data.year == ano
        and op.tipo in ("CLOSED", "OPENED")
    ]

    ganho_usd = sum(op.valor_usd for op in ops_mes)
    tem_day_trade = _detectar_day_trade(ops_mes)
    aliquota = ALIQUOTA_DAY_TRADE if tem_day_trade else ALIQUOTA_NORMAL

    ganho_brl = ganho_usd * ptax

    # Carry Forward: só aplica se houve ganho real
    if ganho_brl > 0 and carry_fwd_brl > 0:
        base_tributavel = max(0.0, ganho_brl - carry_fwd_brl)
    elif ganho_brl > 0:
        base_tributavel = ganho_brl
    else:
        base_tributavel = 0.0

    imposto_brl = base_tributavel * aliquota if base_tributavel > 0 else 0.0
    venc = _vencimento_darf(mes, ano)

    return ResultadoMensal(
        mes=mes, ano=ano,
        ganho_usd=ganho_usd,
        ptax=ptax,
        ganho_brl=ganho_brl,
        carry_fwd_brl=carry_fwd_brl,
        base_tributavel_brl=base_tributavel,
        aliquota=aliquota,
        imposto_brl=imposto_brl,
        tem_day_trade=tem_day_trade,
        operacoes_count=len([op for op in ops_mes if op.tipo == "CLOSED"]),
        vencimento_darf=venc,
    )

def _vencimento_darf(mes: int, ano: int) -> date:
    """Último dia útil do mês seguinte ao mês de apuração."""
    if mes == 12:
        prox_mes, prox_ano = 1, ano + 1
    else:
        prox_mes, prox_ano = mes + 1, ano

    ultimo_dia = date(prox_ano, prox_mes, monthrange(prox_ano, prox_mes)[1])
    while ultimo_dia.weekday() >= 5:
        ultimo_dia -= timedelta(days=1)
    return ultimo_dia

def _detectar_day_trade(operacoes: list) -> bool:
    """
    Detecta day trade: MESMO número de ordem com OPENED e CLOSED no mesmo dia.
    AvaTrade usa números de ordem diferentes para abertura e fechamento, então
    isso só dispara em casos reais de abertura+fechamento com mesmo ID no dia.
    """
    por_ordem_dia: dict = defaultdict(set)
    for op in operacoes:
        m = re.search(r'#(\d+)', op.descricao)
        if not m:
            continue
        chave = (m.group(1), op.data.date())
        por_ordem_dia[chave].add(op.tipo)

    for tipos in por_ordem_dia.values():
        if "OPENED" in tipos and "CLOSED" in tipos:
            return True
    return False

def nome_mes(mes: int) -> str:
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    return meses[mes - 1]
