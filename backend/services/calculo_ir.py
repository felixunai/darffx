"""
Serviço de cálculo de IR para Forex.
- Busca PTAX oficial do Banco Central do Brasil
- Calcula ganho/perda em BRL
- Aplica alíquota correta (15% swap/spot, 20% day trade)
- Regra vigente desde jan/2024: sem isenção, tudo tributado
"""
import httpx
from datetime import date, timedelta
from calendar import monthrange
from typing import Optional
from dataclasses import dataclass

@dataclass
class ResultadoMensal:
    mes: int
    ano: int
    ganho_usd: float
    ptax: float
    ganho_brl: float
    aliquota: float
    imposto_brl: float
    tem_day_trade: bool
    operacoes_count: int

ALIQUOTA_NORMAL    = 0.15   # 15% — operações normais
ALIQUOTA_DAY_TRADE = 0.20   # 20% — day trade

async def buscar_ptax(mes: int, ano: int) -> Optional[float]:
    """
    Busca a PTAX de fechamento do último dia útil do mês.
    Fonte: API oficial do Banco Central do Brasil.
    Retenta até 5 dias úteis anteriores caso não haja cotação.
    """
    # último dia do mês
    ultimo_dia = date(ano, mes, monthrange(ano, mes)[1])

    async with httpx.AsyncClient(timeout=10.0) as client:
        for delta in range(0, 6):
            dia = ultimo_dia - timedelta(days=delta)
            # pula fins de semana
            if dia.weekday() >= 5:
                continue

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
    operacoes_fechadas: list,
    ptax: float,
    mes: int,
    ano: int,
) -> ResultadoMensal:
    """
    Recebe lista de Operacao (tipo CLOSED), PTAX e mês/ano.
    Retorna ResultadoMensal com todos os valores calculados.

    Regra 2024+:
    - Ganhos = soma de CLOSED positivos do mês
    - Perdas = soma de CLOSED negativos do mês
    - Base = ganhos - perdas (se positivo)
    - Alíquota = 15% normal / 20% se houver day trade
    - Sem isenção
    """
    # filtra apenas operações do mês/ano correto
    ops_mes = [
        op for op in operacoes_fechadas
        if op.data.month == mes and op.data.year == ano and op.tipo == "CLOSED"
    ]

    ganho_usd = sum(op.valor_usd for op in ops_mes)
    tem_day_trade = _detectar_day_trade(ops_mes)

    if ganho_usd <= 0:
        # prejuízo ou zero: sem imposto
        return ResultadoMensal(
            mes=mes, ano=ano,
            ganho_usd=ganho_usd,
            ptax=ptax,
            ganho_brl=ganho_usd * ptax,
            aliquota=ALIQUOTA_NORMAL,
            imposto_brl=0.0,
            tem_day_trade=tem_day_trade,
            operacoes_count=len(ops_mes),
        )

    aliquota = ALIQUOTA_DAY_TRADE if tem_day_trade else ALIQUOTA_NORMAL
    ganho_brl = ganho_usd * ptax
    imposto_brl = ganho_brl * aliquota

    return ResultadoMensal(
        mes=mes, ano=ano,
        ganho_usd=ganho_usd,
        ptax=ptax,
        ganho_brl=ganho_brl,
        aliquota=aliquota,
        imposto_brl=imposto_brl,
        tem_day_trade=tem_day_trade,
        operacoes_count=len(ops_mes),
    )

def _detectar_day_trade(operacoes: list) -> bool:
    """
    Detecta se há day trade: mesmo dia com OPENED e CLOSED.
    Requer ambos os tipos para considerar day trade real.
    """
    from collections import defaultdict
    por_dia: dict = defaultdict(set)
    for op in operacoes:
        por_dia[op.data.date()].add(op.tipo)

    for tipos in por_dia.values():
        if "OPENED" in tipos and "CLOSED" in tipos:
            return True
    return False

def nome_mes(mes: int) -> str:
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    return meses[mes - 1]
