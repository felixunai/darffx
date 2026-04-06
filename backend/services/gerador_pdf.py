"""
Gerador de relatório PDF do DarfFX.
Gera documento com resumo do mês, detalhamento das operações e valor do DARF.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from io import BytesIO
from datetime import date
from .calculo_ir import ResultadoMensal, nome_mes

VERDE   = colors.HexColor("#00b87a")
ESCURO  = colors.HexColor("#0a0e17")
CINZA   = colors.HexColor("#6b7a99")
BRANCO  = colors.white
LARANJA = colors.HexColor("#ff6b35")

def gerar_relatorio_pdf(resultado: ResultadoMensal, nome_usuario: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    elementos = []

    # ── CABEÇALHO ──────────────────────────────────────────────
    titulo_style = ParagraphStyle(
        "titulo", parent=styles["Normal"],
        fontSize=22, fontName="Helvetica-Bold",
        textColor=ESCURO, spaceAfter=4
    )
    sub_style = ParagraphStyle(
        "sub", parent=styles["Normal"],
        fontSize=11, textColor=CINZA, spaceAfter=2
    )
    label_style = ParagraphStyle(
        "label", parent=styles["Normal"],
        fontSize=9, textColor=CINZA,
        fontName="Helvetica"
    )
    valor_style = ParagraphStyle(
        "valor", parent=styles["Normal"],
        fontSize=20, fontName="Helvetica-Bold",
        textColor=ESCURO
    )

    elementos.append(Paragraph("DarfFX", titulo_style))
    elementos.append(Paragraph("Relatório de Imposto de Renda — Forex", sub_style))
    elementos.append(HRFlowable(width="100%", thickness=1, color=VERDE, spaceAfter=16))

    # ── DADOS DO MÊS ───────────────────────────────────────────
    mes_label = f"{nome_mes(resultado.mes)} / {resultado.ano}"
    vencimento = _calcular_vencimento(resultado.mes, resultado.ano)

    info_data = [
        ["Competência", "Trader", "Corretora", "Vencimento DARF"],
        [mes_label, nome_usuario, "AvaTrade", vencimento],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 5*cm, 4*cm, 4*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#f4f6fa")),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 9),
        ("TEXTCOLOR",    (0,0), (-1,0), CINZA),
        ("TEXTCOLOR",    (0,1), (-1,1), ESCURO),
        ("ALIGN",        (0,0), (-1,-1), "LEFT"),
        ("PADDING",      (0,0), (-1,-1), 8),
        ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#e0e4ee")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [BRANCO]),
    ]))
    elementos.append(info_table)
    elementos.append(Spacer(1, 20))

    # ── CARDS DE RESUMO ─────────────────────────────────────────
    sinal_ganho = "+" if resultado.ganho_usd >= 0 else ""
    cards_data = [
        ["Resultado (USD)", "PTAX (último dia útil)", "Resultado (BRL)", "Imposto Devido"],
        [
            f"{sinal_ganho}US$ {resultado.ganho_usd:,.2f}",
            f"R$ {resultado.ptax:.4f}",
            f"R$ {resultado.ganho_brl:,.2f}",
            f"R$ {resultado.imposto_brl:,.2f}",
        ],
    ]
    cards_table = Table(cards_data, colWidths=[4.25*cm]*4)
    imposto_cor = VERDE if resultado.imposto_brl == 0 else LARANJA
    cards_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#f4f6fa")),
        ("BACKGROUND",   (3,1), (3,1), colors.HexColor("#fff8f5")),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",     (0,1), (-1,1), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,0), 9),
        ("FONTSIZE",     (0,1), (-1,1), 13),
        ("TEXTCOLOR",    (0,0), (-1,0), CINZA),
        ("TEXTCOLOR",    (0,1), (2,1), ESCURO),
        ("TEXTCOLOR",    (3,1), (3,1), imposto_cor),
        ("ALIGN",        (0,0), (-1,-1), "CENTER"),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("PADDING",      (0,0), (-1,-1), 10),
        ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#e0e4ee")),
    ]))
    elementos.append(cards_table)
    elementos.append(Spacer(1, 24))

    # ── BOX DARF ───────────────────────────────────────────────
    if resultado.imposto_brl > 0:
        aliq_pct = int(resultado.aliquota * 100)
        tipo_op  = "Day Trade" if resultado.tem_day_trade else "Operação Normal"
        darf_data = [
            ["DARF — Documento de Arrecadação de Receitas Federais"],
            [f"Código: 8523  |  Período: {mes_label}  |  Tipo: {tipo_op} ({aliq_pct}%)  |  Vencimento: {vencimento}"],
            [f"VALOR A PAGAR:  R$ {resultado.imposto_brl:,.2f}"],
        ]
        darf_table = Table(darf_data, colWidths=[17*cm])
        darf_table.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0), ESCURO),
            ("BACKGROUND",   (0,1), (-1,1), colors.HexColor("#1a2235")),
            ("BACKGROUND",   (0,2), (-1,2), colors.HexColor("#fff8f5")),
            ("FONTNAME",     (0,0), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,0), 11),
            ("FONTSIZE",     (0,1), (-1,1), 9),
            ("FONTSIZE",     (0,2), (-1,2), 16),
            ("TEXTCOLOR",    (0,0), (-1,0), VERDE),
            ("TEXTCOLOR",    (0,1), (-1,1), colors.HexColor("#9aabcc")),
            ("TEXTCOLOR",    (0,2), (-1,2), LARANJA),
            ("ALIGN",        (0,0), (-1,-1), "CENTER"),
            ("PADDING",      (0,0), (-1,-1), 12),
        ]))
        elementos.append(darf_table)
        elementos.append(Spacer(1, 8))

        aviso_style = ParagraphStyle("aviso", parent=styles["Normal"],
            fontSize=8, textColor=CINZA, alignment=TA_CENTER)
        elementos.append(Paragraph(
            "⚠️  Pague o DARF pelo aplicativo do seu banco usando o código 8523. "
            "Pagamento após o vencimento gera multa de 0,33%/dia + SELIC.",
            aviso_style
        ))
    else:
        sem_imposto = Table(
            [["✓ Sem imposto a pagar neste mês (resultado negativo ou zero)"]],
            colWidths=[17*cm]
        )
        sem_imposto.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f0fdf4")),
            ("FONTNAME",   (0,0), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 11),
            ("TEXTCOLOR",  (0,0), (-1,-1), VERDE),
            ("ALIGN",      (0,0), (-1,-1), "CENTER"),
            ("PADDING",    (0,0), (-1,-1), 14),
        ]))
        elementos.append(sem_imposto)

    elementos.append(Spacer(1, 24))

    # ── RODAPÉ ─────────────────────────────────────────────────
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e0e4ee")))
    rodape_style = ParagraphStyle("rodape", parent=styles["Normal"],
        fontSize=8, textColor=CINZA, alignment=TA_CENTER, spaceBefore=8)
    elementos.append(Paragraph(
        f"Relatório gerado pelo DarfFX em {date.today().strftime('%d/%m/%Y')}  •  "
        "Este documento é informativo. Consulte um contador para casos complexos.",
        rodape_style
    ))

    doc.build(elementos)
    return buffer.getvalue()

def _calcular_vencimento(mes: int, ano: int) -> str:
    """DARF vence no último dia útil do mês seguinte."""
    from calendar import monthrange
    proximo_mes = mes + 1
    proximo_ano = ano
    if proximo_mes > 12:
        proximo_mes = 1
        proximo_ano += 1

    ultimo_dia = monthrange(proximo_ano, proximo_mes)[1]
    venc = date(proximo_ano, proximo_mes, ultimo_dia)

    # recua até dia útil
    while venc.weekday() >= 5:
        venc = venc - __import__("datetime").timedelta(days=1)

    return venc.strftime("%d/%m/%Y")
