"""
Gerador de PDF do Painel Executivo ICB — uma página, layout escuro em duas colunas.
Replica o design de referência usando ReportLab canvas drawing.
"""
import io
import datetime as dt
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color


# ─── Paleta de cores ─────────────────────────────────────────────────────────
BG          = HexColor('#061628')
PANEL_BG    = HexColor('#0c2240')
PANEL_BG2   = HexColor('#0a1d38')
BORDER      = HexColor('#1e3d6e')
BORDER_LIGHT= HexColor('#1a3560')
HEADER_BG   = HexColor('#082040')

WHITE       = HexColor('#f8fafc')
SLATE_200   = HexColor('#cbd5e1')
SLATE_400   = HexColor('#94a3b8')
SLATE_500   = HexColor('#64748b')
CYAN        = HexColor('#38bdf8')
CYAN_DIM    = HexColor('#0ea5e9')
GREEN       = HexColor('#4ade80')
GREEN_DIM   = HexColor('#166534')
RED         = HexColor('#f87171')
RED_DIM     = HexColor('#7f1d1d')
AMBER       = HexColor('#fbbf24')
AMBER_DIM   = HexColor('#713f12')
ORANGE      = HexColor('#fb923c')
ORANGE_DIM  = HexColor('#7c2d12')
GOLD        = HexColor('#eab308')
GOLD_DIM    = HexColor('#854d0e')


# ─── Helpers ──────────────────────────────────────────────────────────────────
def money(v):
    if v is None:
        return 'n/d'
    return f'R$ {abs(v):,.0f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def money_k(v):
    if v is None:
        return 'n/d'
    k = v / 1000
    return f'R$ {k:,.0f}k'.replace(',', 'X').replace('.', ',').replace('X', '.')


def pct(v):
    if v is None:
        return 'n/d'
    return f'{v * 100:+.1f}%'


def pct_plain(v):
    if v is None:
        return 'n/d'
    return f'{v * 100:.1f}%'


def delta_color(v):
    if v is None:
        return SLATE_400
    return GREEN if v >= 0 else RED


# ─── Drawing primitives ───────────────────────────────────────────────────────
def rounded_rect(c, x, y, w, h, r=6, fill_color=PANEL_BG, stroke_color=BORDER, stroke_width=0.5):
    c.saveState()
    c.setFillColor(fill_color)
    c.setStrokeColor(stroke_color)
    c.setLineWidth(stroke_width)
    c.roundRect(x, y, w, h, r, fill=1, stroke=1)
    c.restoreState()


def label(c, text, x, y, size=7, color=SLATE_400, font='Helvetica-Bold'):
    c.saveState()
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, text)
    c.restoreState()


def label_right(c, text, x, y, size=7, color=SLATE_400, font='Helvetica'):
    c.saveState()
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawRightString(x, y, text)
    c.restoreState()


def section_title(c, text, x, y, w, color=CYAN):
    c.saveState()
    c.setFont('Helvetica-Bold', 6.5)
    c.setFillColor(color)
    c.drawString(x + 5, y - 9, text.upper())
    c.setStrokeColor(BORDER_LIGHT)
    c.setLineWidth(0.4)
    c.line(x, y - 12, x + w, y - 12)
    c.restoreState()
    return y - 16


def divider(c, x, y, w):
    c.saveState()
    c.setStrokeColor(BORDER_LIGHT)
    c.setLineWidth(0.3)
    c.line(x, y, x + w, y)
    c.restoreState()


def bullet_circle(c, x, y, r, color):
    c.saveState()
    c.setFillColor(color)
    c.circle(x, y, r, fill=1, stroke=0)
    c.restoreState()


# ─── Main PDF generator ───────────────────────────────────────────────────────
def generate_executive_dashboard_pdf(data: dict) -> bytes:
    PAGE_W, PAGE_H = landscape(A4)   # 841.89 x 595.28 pt
    M = 14                            # margin

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))

    # Background
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # ── Header bar ────────────────────────────────────────────────────────────
    HDR_H = 32
    HDR_Y = PAGE_H - HDR_H
    c.setFillColor(HEADER_BG)
    c.rect(0, HDR_Y, PAGE_W, HDR_H, fill=1, stroke=0)
    c.setStrokeColor(CYAN_DIM)
    c.setLineWidth(0.5)
    c.line(0, HDR_Y, PAGE_W, HDR_Y)

    # ICB logo — left
    c.setFont('Helvetica-Bold', 15)
    c.setFillColor(CYAN)
    c.drawString(M, HDR_Y + 9, '≋ ICB')

    # Title — right
    resumo = data.get('resumo_executivo', {})
    header = data.get('header', {})
    periodo = header.get('periodo_referencia_label') or header.get('periodo_referencia', 'Q1 2026')
    c.setFont('Helvetica-Bold', 10)
    c.setFillColor(WHITE)
    title_text = f'Painel Executivo  –  {periodo}'
    c.drawRightString(PAGE_W - M, HDR_Y + 9, title_text)

    # Status badge
    status = header.get('status', 'atualizado')
    status_label = {'atualizado': 'Dados Confiáveis', 'atencao': 'Atenção', 'desatualizado': 'Desatualizado'}.get(status, status)
    status_color = {'atualizado': GREEN, 'atencao': AMBER, 'desatualizado': RED}.get(status, SLATE_400)
    c.setFont('Helvetica-Bold', 6.5)
    c.setFillColor(status_color)
    c.drawRightString(PAGE_W - M, HDR_Y + 21, f'● {status_label}')

    # ── Layout geometry ────────────────────────────────────────────────────────
    CONTENT_TOP = HDR_Y - 8
    CONTENT_BOT = M
    CONTENT_H   = CONTENT_TOP - CONTENT_BOT

    COL_GAP  = 8
    L_W      = 286           # left column width
    R_X      = M + L_W + COL_GAP
    R_W      = PAGE_W - M - R_X
    L_X      = M

    # ══════════════════════════════════════════════════════════════════════════
    # LEFT COLUMN
    # ══════════════════════════════════════════════════════════════════════════
    cy = CONTENT_TOP    # cursor y (decreases as we draw down)

    # ── 1. RESUMO EXECUTIVO ──────────────────────────────────────────────────
    BOX1_H = 138
    BOX1_Y = cy - BOX1_H
    rounded_rect(c, L_X, BOX1_Y, L_W, BOX1_H)
    cy2 = BOX1_Y + BOX1_H - 6
    cy2 = section_title(c, 'Resumo Executivo', L_X, cy2, L_W)

    rb = resumo.get('receita_bruta', 0)
    eb = resumo.get('ebitda', 0)
    ll = resumo.get('lucro_liquido', 0)
    vqoq = resumo.get('variacao_qoq', {}) or {}
    vyoy = resumo.get('variacao_yoy', {}) or {}

    rows = [
        ('Receita Bruta', rb, vyoy.get('receita_bruta'), 'YoY', vqoq.get('receita_bruta'), 'QoQ'),
        ('EBITDA',        eb, vqoq.get('ebitda'),        'QoQ', vyoy.get('ebitda'),        'YoY'),
        ('Lucro Líquido', ll, vyoy.get('lucro_liquido'),  'YoY', vqoq.get('lucro_liquido'), 'QoQ'),
    ]

    for row_label, val, d1, l1, d2, l2 in rows:
        cy2 -= 4
        label(c, row_label, L_X + 5, cy2, 6.5, SLATE_400)
        # main value
        c.setFont('Helvetica-Bold', 9)
        c.setFillColor(WHITE)
        c.drawString(L_X + 70, cy2, money(val))
        # deltas
        if d1 is not None:
            txt = f'{pct(d1)} {l1}'
            c.setFont('Helvetica', 6.5)
            c.setFillColor(delta_color(d1))
            c.drawString(L_X + 168, cy2, txt)
        if d2 is not None:
            txt = f'{pct(d2)} {l2}'
            c.setFont('Helvetica', 6.5)
            c.setFillColor(delta_color(d2))
            c.drawString(L_X + 225, cy2, txt)
        cy2 -= 2
        divider(c, L_X + 4, cy2, L_W - 8)
        cy2 -= 8

    # Saúde da Rede
    cy2 -= 2
    saude = resumo.get('saude_rede', {})
    label(c, 'Saúde da Rede', L_X + 5, cy2, 6.5, SLATE_400)
    sx = L_X + 70
    items_s = [
        (str(saude.get('saudaveis', 0)), '✓', GREEN),
        (str(saude.get('atencao', 0)),   '!', AMBER),
        (str(saude.get('risco', 0)),     '!', ORANGE),
    ]
    for sval, sicon, scol in items_s:
        bullet_circle(c, sx + 5, cy2 + 2.5, 5, scol)
        c.setFont('Helvetica-Bold', 8)
        c.setFillColor(WHITE)
        c.drawString(sx + 12, cy2 - 0.5, sval)
        sx += 28
    c.setFont('Helvetica', 6.5)
    c.setFillColor(SLATE_400)
    enc = saude.get('encerradas', 0)
    c.drawString(sx, cy2, f'{enc} Enc.')

    # last update
    cy2 -= 13
    lu = header.get('last_update')
    if lu:
        try:
            lu_dt = dt.datetime.fromisoformat(lu)
            lu_str = lu_dt.strftime('%d/%m às %H:%M')
        except Exception:
            lu_str = str(lu)[:16]
    else:
        lu_str = 'n/d'
    c.setFont('Helvetica', 6)
    c.setFillColor(SLATE_500)
    c.drawString(L_X + 5, cy2, f'↻ Última atualização: {lu_str}')

    cy = BOX1_Y - 6

    # ── 2. DRE CONSOLIDADA ───────────────────────────────────────────────────
    BOX2_H = 100
    BOX2_Y = cy - BOX2_H
    rounded_rect(c, L_X, BOX2_Y, L_W, BOX2_H)
    cy2 = BOX2_Y + BOX2_H - 6
    cy2 = section_title(c, 'DRE Consolidada', L_X, cy2, L_W)

    # Column headers
    c.setFont('Helvetica-Bold', 5.5)
    c.setFillColor(SLATE_500)
    c.drawRightString(L_X + L_W - 5,  cy2, 'Vs. Ano Ant.')
    c.drawRightString(L_X + L_W - 55, cy2, 'Vs. Trim. Ant.')
    cy2 -= 10

    dre = data.get('dre_consolidada', {}).get('linhas', [])
    dre_keys = ['Receita Líquida', '(-) Custos/Despesas', 'EBITDA', 'Lucro Líquido']
    for linha in dre:
        if linha.get('linha') not in dre_keys:
            continue
        nome = linha['linha'].replace('(-) ', '(-) ')
        val  = linha.get('valor_atual', 0)
        qoq  = linha.get('variacao_qoq')
        yoy  = linha.get('variacao_yoy')

        c.setFont('Helvetica', 7)
        c.setFillColor(SLATE_200)
        c.drawString(L_X + 5, cy2, nome)
        c.setFont('Helvetica-Bold', 7)
        c.setFillColor(WHITE)
        c.drawString(L_X + 92, cy2, money(val))

        # QoQ
        if qoq is not None:
            c.setFont('Helvetica', 6.5)
            c.setFillColor(delta_color(qoq))
            arrow = '▲' if qoq >= 0 else '▼'
            c.drawRightString(L_X + L_W - 55, cy2, f'{pct(qoq)} {arrow}')
        else:
            c.setFont('Helvetica', 6.5)
            c.setFillColor(SLATE_500)
            c.drawRightString(L_X + L_W - 55, cy2, '—')

        # YoY
        if yoy is not None:
            c.setFont('Helvetica', 6.5)
            c.setFillColor(delta_color(yoy))
            arrow = '▲' if yoy >= 0 else '▼'
            c.drawRightString(L_X + L_W - 5, cy2, f'{pct(yoy)} {arrow}')
        else:
            c.setFont('Helvetica', 6.5)
            c.setFillColor(SLATE_500)
            c.drawRightString(L_X + L_W - 5, cy2, '—')

        cy2 -= 2
        divider(c, L_X + 4, cy2, L_W - 8)
        cy2 -= 11

    cy = BOX2_Y - 6

    # ── 3. INDICADORES OPERACIONAIS ──────────────────────────────────────────
    BOX3_H = CONTENT_BOT + (cy - CONTENT_BOT)
    BOX3_Y = CONTENT_BOT
    rounded_rect(c, L_X, BOX3_Y, L_W, BOX3_H)
    cy2 = BOX3_Y + BOX3_H - 6
    cy2 = section_title(c, 'Indicadores Operacionais', L_X, cy2, L_W)

    indicadores = data.get('indicadores_operacionais', {})
    conv   = indicadores.get('conversao_media_rede')
    ticket = indicadores.get('ticket_medio_rede')
    uc_conv = indicadores.get('unidade_critica_conversao', {}) or {}
    uc_tick = indicadores.get('unidade_ticket_abaixo', {}) or {}

    cy2 -= 2
    # Conversão
    label(c, 'Conversão média', L_X + 5, cy2, 6.5, SLATE_400)
    c.setFont('Helvetica-Bold', 9)
    c.setFillColor(WHITE)
    c.drawString(L_X + 80, cy2, pct_plain(conv) if conv else 'n/d')
    if uc_conv.get('unidade'):
        c.setFont('Helvetica', 6)
        c.setFillColor(RED)
        c.drawString(L_X + 132, cy2, f'▼ {uc_conv["unidade"]}: {pct_plain(uc_conv.get("valor"))}')

    cy2 -= 14
    # Ticket Médio
    label(c, 'Ticket médio', L_X + 5, cy2, 6.5, SLATE_400)
    c.setFont('Helvetica-Bold', 9)
    c.setFillColor(WHITE)
    c.drawString(L_X + 80, cy2, money(ticket) if ticket else 'n/d')
    if uc_tick.get('unidade'):
        c.setFont('Helvetica', 6)
        c.setFillColor(RED)
        c.drawString(L_X + 132, cy2, f'▼ {uc_tick["unidade"]}: {money(uc_tick.get("valor"))}')

    # Pipeline highlight in this box too
    pipeline = data.get('pipeline_financeiro', {})
    cy2 -= 16
    divider(c, L_X + 4, cy2, L_W - 8)
    cy2 -= 8
    label(c, 'Pipeline Financeiro', L_X + 5, cy2, 6.5, CYAN)
    cy2 -= 11
    pip_items = [
        ('Leads Ativos', f'{int(pipeline.get("leads_ativos",0)):,}'.replace(',','.')),
        ('Cirurgias Esperadas', str(pipeline.get('cirurgias_esperadas','n/d'))),
        ('Potencial de Receita', money_k(pipeline.get('potencial_receita'))),
    ]
    for pk, pv in pip_items:
        label(c, pk, L_X + 5, cy2, 6.5, SLATE_400)
        c.setFont('Helvetica-Bold', 8)
        c.setFillColor(CYAN)
        c.drawRightString(L_X + L_W - 5, cy2, pv)
        cy2 -= 11

    # ══════════════════════════════════════════════════════════════════════════
    # RIGHT COLUMN
    # ══════════════════════════════════════════════════════════════════════════
    cy = CONTENT_TOP

    # ── 4. ALERTAS E AÇÕES ───────────────────────────────────────────────────
    alertas = data.get('alertas', {})
    alert_items = alertas.get('items', [])
    avaliacao  = alertas.get('avaliacao_fechamento', [])

    ALERT_H = 130
    ALERT_Y = cy - ALERT_H
    rounded_rect(c, R_X, ALERT_Y, R_W, ALERT_H)
    cy2 = ALERT_Y + ALERT_H - 6
    cy2 = section_title(c, 'Alertas e Ações', R_X, cy2, R_W)

    # Right sub-panel: Unidades a avaliar
    SUB_W = 130
    SUB_X = R_X + R_W - SUB_W - 4
    SUB_Y = cy2 - (len(avaliacao) * 14 + 8)
    if SUB_Y < ALERT_Y + 4:
        SUB_Y = ALERT_Y + 4
    rounded_rect(c, SUB_X, SUB_Y, SUB_W, cy2 - SUB_Y + 2, r=4,
                 fill_color=PANEL_BG2, stroke_color=BORDER_LIGHT, stroke_width=0.3)
    c.setFont('Helvetica-Bold', 5.5)
    c.setFillColor(SLATE_400)
    c.drawString(SUB_X + 4, cy2 - 2, 'UNIDADES A AVALIAR')
    uy = cy2 - 13
    for av in avaliacao[:4]:
        bullet_circle(c, SUB_X + 8, uy + 2.5, 2.5, RED)
        c.setFont('Helvetica', 6.5)
        c.setFillColor(WHITE)
        c.drawString(SUB_X + 14, uy, av.get('unidade', ''))
        uy -= 12

    # Alert cards (left part)
    ALERT_CARD_W = R_W - SUB_W - 12
    nivel_styles = {
        'critico': (RED_DIM, RED, '●'),
        'atencao': (GOLD_DIM, GOLD, '⚠'),
        'positivo': (GREEN_DIM, GREEN, '✓'),
    }
    ay = cy2 - 2
    for alert in alert_items[:3]:
        nivel = alert.get('nivel', 'info')
        bg_c, fg_c, icon = nivel_styles.get(nivel, (PANEL_BG2, CYAN, '●'))
        card_h = 28
        card_y = ay - card_h
        if card_y < ALERT_Y + 4:
            break
        rounded_rect(c, R_X + 4, card_y, ALERT_CARD_W - 4, card_h, r=4,
                     fill_color=bg_c, stroke_color=fg_c, stroke_width=0.6)
        c.setFont('Helvetica-Bold', 6.5)
        c.setFillColor(fg_c)
        titulo = alert.get('titulo', '')[:45]
        c.drawString(R_X + 10, ay - 10, f'{icon}  {titulo}')
        detalhe = alert.get('detalhe', '')[:60]
        c.setFont('Helvetica', 5.5)
        c.setFillColor(SLATE_200)
        c.drawString(R_X + 10, ay - 20, detalhe)
        ay -= card_h + 3

    cy = ALERT_Y - 6

    # ── 5. RANKING DE UNIDADES ────────────────────────────────────────────────
    ranking = data.get('ranking', {})
    top5    = ranking.get('top_5', [])
    bot5    = ranking.get('bottom_5', [])

    RANK_H = 100
    RANK_Y = cy - RANK_H
    rounded_rect(c, R_X, RANK_Y, R_W, RANK_H)
    cy2 = RANK_Y + RANK_H - 6
    cy2 = section_title(c, 'Ranking de Unidades  –  EBITDA', R_X, cy2, R_W)

    col_w = (R_W - 10) / 2
    # Sub-headers
    c.saveState()
    c.setFillColor(GREEN_DIM)
    c.roundRect(R_X + 4, cy2 - 14, col_w - 2, 12, 3, fill=1, stroke=0)
    c.setFillColor(RED_DIM)
    c.roundRect(R_X + 4 + col_w + 2, cy2 - 14, col_w - 2, 12, 3, fill=1, stroke=0)
    c.restoreState()
    c.setFont('Helvetica-Bold', 6.5)
    c.setFillColor(GREEN)
    c.drawCentredString(R_X + 4 + col_w / 2, cy2 - 9, 'TOP 5 EBITDA')
    c.setFillColor(RED)
    c.drawCentredString(R_X + 4 + col_w + 2 + col_w / 2, cy2 - 9, 'BOTTOM 5 EBITDA')
    cy2 -= 18

    max_rows = min(5, len(top5), len(bot5))
    for i in range(max_rows):
        # TOP
        t = top5[i]
        c.setFont('Helvetica-Bold', 6.5)
        c.setFillColor(WHITE)
        c.drawString(R_X + 8, cy2, f'{i+1}. {t["unidade"]}')
        c.setFont('Helvetica', 6)
        c.setFillColor(GREEN)
        c.drawRightString(R_X + 4 + col_w - 2, cy2, money_k(t['valor']))
        # BOTTOM
        b = bot5[i]
        c.setFont('Helvetica-Bold', 6.5)
        c.setFillColor(WHITE)
        c.drawString(R_X + 8 + col_w + 2, cy2, f'{i+1}. {b["unidade"]}')
        c.setFont('Helvetica', 6)
        c.setFillColor(RED if b['valor'] < 0 else SLATE_200)
        c.drawRightString(R_X + R_W - 4, cy2, money_k(b['valor']))
        cy2 -= 12

    cy = RANK_Y - 6

    # ── 6. QUALIDADE DE DADOS ─────────────────────────────────────────────────
    qual = data.get('qualidade_dados', {})
    flags = qual.get('flags', [])
    obs   = qual.get('observacoes', [])
    all_issues = flags + obs

    QUAL_H = max(26, 18 + len(all_issues) * 10)
    QUAL_H = min(QUAL_H, 38)
    QUAL_Y = CONTENT_BOT
    rounded_rect(c, R_X, QUAL_Y, R_W, QUAL_H, fill_color=AMBER_DIM, stroke_color=AMBER, stroke_width=0.5)
    cy2 = QUAL_Y + QUAL_H - 6
    c.setFont('Helvetica-Bold', 6.5)
    c.setFillColor(AMBER)
    c.drawString(R_X + 6, cy2, '⚠  QUALIDADE DE DADOS')
    cy2 -= 10
    for flag in all_issues[:2]:
        c.setFont('Helvetica', 6)
        c.setFillColor(SLATE_200)
        c.drawString(R_X + 12, cy2, f'• {flag[:80]}')
        cy2 -= 9
    if not all_issues:
        c.setFont('Helvetica', 6)
        c.setFillColor(GREEN)
        c.drawString(R_X + 12, cy2, '✓ Sem inconsistências detectadas')

    cy = QUAL_Y + QUAL_H + 6

    # ── 7. EXPOSIÇÃO FISCAL (between ranking and qualidade) ───────────────────
    FISCAL_H = cy - RANK_Y - 12
    FISCAL_Y = QUAL_Y + QUAL_H + 4
    if FISCAL_H > 10:
        rounded_rect(c, R_X, FISCAL_Y, R_W, FISCAL_H,
                     fill_color=ORANGE_DIM, stroke_color=ORANGE, stroke_width=0.4)
        c.setFont('Helvetica-Bold', 6.5)
        c.setFillColor(ORANGE)
        c.drawString(R_X + 6, FISCAL_Y + FISCAL_H - 8, '⚠  EXPOSIÇÃO FISCAL')
        c.setFont('Helvetica', 6)
        c.setFillColor(SLATE_200)
        c.drawString(R_X + 12, FISCAL_Y + FISCAL_H - 18, 'Verifique as obrigações fiscais pendentes')

    # ── Footer ────────────────────────────────────────────────────────────────
    c.setFont('Helvetica', 5)
    c.setFillColor(SLATE_500)
    gerado = dt.datetime.now().strftime('%d/%m/%Y %H:%M')
    c.drawString(M, 5, f'ICB · Executive Finance Control · Uso interno · Confidencial · Gerado em {gerado}')
    c.drawRightString(PAGE_W - M, 5, 'Página 1 de 1')

    c.save()
    return buf.getvalue()
