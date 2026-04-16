"""
Gerador de PDF do Painel Executivo ICB — uma página A4 paisagem.
Layout idêntico ao mockup de referência: header com logo + título, duas colunas
(esquerda = Resumo / DRE / Indicadores; direita = Alertas+Avaliação / Ranking+Pipeline / Qualidade).
"""
import io
import datetime as dt
from pathlib import Path
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.utils import ImageReader


BG          = HexColor('#0a1f3d')
PANEL_BG    = HexColor('#0f2a4f')
PANEL_BG2   = HexColor('#0a223f')
BORDER      = HexColor('#1e3d6e')
BORDER_SOFT = HexColor('#1a3560')
HDR_BG      = HexColor('#0c2547')

WHITE       = HexColor('#f8fafc')
SLATE_100   = HexColor('#e2e8f0')
SLATE_200   = HexColor('#cbd5e1')
SLATE_300   = HexColor('#94a3b8')
SLATE_500   = HexColor('#64748b')

CYAN        = HexColor('#38bdf8')
CYAN_DIM    = HexColor('#0ea5e9')

GREEN       = HexColor('#4ade80')
GREEN_DIM   = HexColor('#166534')

AMBER       = HexColor('#fbbf24')
AMBER_DIM   = HexColor('#713f12')
AMBER_BG    = HexColor('#3b2a08')

RED         = HexColor('#f87171')
RED_DIM     = HexColor('#7f1d1d')
RED_BG      = HexColor('#3b1212')

GOLD        = HexColor('#eab308')
GOLD_BG     = HexColor('#3a2c08')


# ─────────────────────────────────────────── helpers ────────────────────────
def money(v):
    if v is None: return 'n/d'
    return f'R$ {abs(v):,.0f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def money_signed(v):
    if v is None: return 'n/d'
    sign = '-' if v < 0 else ''
    return f'{sign}R$ {abs(v):,.0f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def money_k(v):
    if v is None: return 'n/d'
    return f'{v/1000:,.0f}k'.replace(',', '.')


def money_mm(v):
    if v is None: return 'n/d'
    return f'R$ {v/1_000_000:.1f} MM'.replace('.', ',')


def pct(v):
    if v is None: return ''
    return f'{v*100:+.1f}%'


def pct_plain(v):
    if v is None: return 'n/d'
    return f'{v*100:.1f}%'


def delta_color(v):
    if v is None: return SLATE_300
    return GREEN if v >= 0 else RED


def delta_arrow(v):
    if v is None: return ''
    return '▲' if v >= 0 else '▼'


def rect(c, x, y, w, h, r=8, fill=PANEL_BG, stroke=BORDER, sw=0.6):
    c.saveState()
    c.setFillColor(fill); c.setStrokeColor(stroke); c.setLineWidth(sw)
    c.roundRect(x, y, w, h, r, fill=1, stroke=1)
    c.restoreState()


def section_title(c, text, x, y, w, color=CYAN, size=8.5):
    c.saveState()
    c.setFont('Helvetica-Bold', size); c.setFillColor(color)
    c.drawString(x + 10, y - 12, text.upper())
    c.setStrokeColor(BORDER_SOFT); c.setLineWidth(0.4)
    c.line(x + 10, y - 17, x + w - 10, y - 17)
    c.restoreState()
    return y - 22


def text_at(c, s, x, y, size=7, color=WHITE, font='Helvetica', anchor='left'):
    c.saveState()
    c.setFont(font, size); c.setFillColor(color)
    if anchor == 'right':
        c.drawRightString(x, y, s)
    elif anchor == 'center':
        c.drawCentredString(x, y, s)
    else:
        c.drawString(x, y, s)
    c.restoreState()


def filled_circle(c, x, y, r, color):
    c.saveState(); c.setFillColor(color)
    c.circle(x, y, r, fill=1, stroke=0); c.restoreState()


def pill(c, x, y, w, h, fill_color, stroke_color):
    rect(c, x, y, w, h, r=h/2, fill=fill_color, stroke=stroke_color, sw=0.7)


def _draw_logo(c, x, y, w, h):
    p = Path('/home/runner/workspace/attached_assets/icb_logo_FINAL-04_1776303551842.png')
    if p.exists():
        c.drawImage(ImageReader(str(p)), x, y, width=w, height=h, mask='auto', preserveAspectRatio=True, anchor='sw')
    else:
        text_at(c, 'ICB', x, y + 6, 16, CYAN, 'Helvetica-Bold')


# ─────────────────────────────────────────── main ───────────────────────────
def generate_executive_dashboard_pdf(data: dict) -> bytes:
    PW, PH = landscape(A4)   # 842 x 595
    M = 14

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PW, PH))

    # background
    c.setFillColor(BG); c.rect(0, 0, PW, PH, fill=1, stroke=0)

    # ── header ──────────────────────────────────────────────────────────────
    HDR_H = 38
    HDR_Y = PH - HDR_H
    c.setFillColor(HDR_BG); c.rect(0, HDR_Y, PW, HDR_H, fill=1, stroke=0)
    c.setStrokeColor(CYAN_DIM); c.setLineWidth(0.7); c.line(0, HDR_Y, PW, HDR_Y)

    _draw_logo(c, M, HDR_Y + 6, 86, 26)

    header = data.get('header', {}) or {}
    periodo = header.get('periodo_referencia_label') or header.get('periodo_referencia', '')
    text_at(c, f'Painel Executivo — {periodo}', PW - M, HDR_Y + 14, 13, WHITE, 'Helvetica-Bold', 'right')

    # ── layout columns ──────────────────────────────────────────────────────
    GAP   = 7
    TOP   = HDR_Y - 6
    BOT   = M + 14   # leave room for footer
    L_X   = M
    L_W   = 408
    R_X   = L_X + L_W + GAP
    R_W   = PW - M - R_X

    # right column heights
    ALT_H = 250
    RKP_H = 165
    QUA_H = (TOP - BOT) - ALT_H - RKP_H - GAP * 2

    ALT_Y = TOP - ALT_H
    RKP_Y = ALT_Y - GAP - RKP_H
    QUA_Y = BOT

    # left column heights
    RES_H = 175
    DRE_H = 195
    IND_H = (TOP - BOT) - RES_H - DRE_H - GAP * 2

    RES_Y = TOP - RES_H
    DRE_Y = RES_Y - GAP - DRE_H
    IND_Y = BOT

    # ── BOX 1: RESUMO EXECUTIVO ─────────────────────────────────────────────
    rect(c, L_X, RES_Y, L_W, RES_H)
    cy = section_title(c, 'Resumo Executivo', L_X, RES_Y + RES_H, L_W)

    resumo = data.get('resumo_executivo', {}) or {}
    rb  = resumo.get('receita_bruta')
    eb  = resumo.get('ebitda')
    ll  = resumo.get('lucro_liquido')
    vqoq = resumo.get('variacao_qoq', {}) or {}
    vyoy = resumo.get('variacao_yoy', {}) or {}

    rows = [
        ('RECEITA BRUTA',  rb, vyoy.get('receita_bruta'), 'YoY'),
        ('EBITDA',         eb, vqoq.get('ebitda'),        'QoQ'),
        ('LUCRO LÍQUIDO',  ll, vyoy.get('lucro_liquido'), 'YoY'),
    ]
    cy -= 6
    for lbl, val, d, dlbl in rows:
        text_at(c, lbl, L_X + 18, cy, 8, SLATE_300, 'Helvetica-Bold')
        text_at(c, money(val), L_X + 165, cy, 11, WHITE, 'Helvetica-Bold')
        if d is not None:
            text_at(c, f'({pct(d)} {dlbl})', L_X + 270, cy, 8, delta_color(d), 'Helvetica')
        cy -= 22

    # Saúde da rede
    saude = resumo.get('saude_rede', {}) or {}
    text_at(c, 'SAÚDE DA REDE', L_X + 18, cy, 8, SLATE_300, 'Helvetica-Bold')
    sx = L_X + 165
    items = [
        (str(saude.get('saudaveis', 0)),  GREEN),
        (str(saude.get('atencao', 0)),    AMBER),
        (str(saude.get('risco', 0)),      RED),
    ]
    for val, col in items:
        filled_circle(c, sx + 6, cy + 3, 5, col)
        text_at(c, val, sx + 16, cy, 10, WHITE, 'Helvetica-Bold')
        sx += 32
    text_at(c, f"{saude.get('encerradas', 0)} Encerradas", sx + 4, cy, 8, SLATE_200, 'Helvetica')

    cy -= 24

    # Pill "Última atualização"
    lu = header.get('last_update')
    try:
        lu_dt = dt.datetime.fromisoformat(lu) if lu else None
        lu_str = lu_dt.strftime('%d/%m às %H:%M') if lu_dt else 'n/d'
    except Exception:
        lu_str = str(lu)[:16] if lu else 'n/d'
    status = header.get('status', 'atualizado')
    status_label = {'atualizado': 'Dados Confiáveis', 'atencao': 'Atenção', 'desatualizado': 'Desatualizado'}.get(status, status)
    status_color = {'atualizado': GREEN, 'atencao': AMBER, 'desatualizado': RED}.get(status, SLATE_300)

    pill_w, pill_h = L_W - 36, 22
    pill_x, pill_y = L_X + 18, cy - 6
    pill(c, pill_x, pill_y, pill_w, pill_h, PANEL_BG2, BORDER_SOFT)
    text_at(c, f'Última atualização: {lu_str}', pill_x + 12, pill_y + 7, 8, SLATE_200)
    text_at(c, f'● {status_label}', pill_x + pill_w - 12, pill_y + 7, 8, status_color, 'Helvetica-Bold', 'right')

    # ── BOX 2: DRE CONSOLIDADA ──────────────────────────────────────────────
    rect(c, L_X, DRE_Y, L_W, DRE_H)
    cy = section_title(c, 'DRE Consolidada', L_X, DRE_Y + DRE_H, L_W)

    text_at(c, 'Vs. Trim. Ant.', L_X + L_W - 105, cy - 6, 7, SLATE_300, 'Helvetica-Bold', 'right')
    text_at(c, 'Vs. Ano Ant.',   L_X + L_W - 18,  cy - 6, 7, SLATE_300, 'Helvetica-Bold', 'right')
    cy -= 16

    dre = data.get('dre_consolidada', {}).get('linhas', []) or []
    label_map = {
        'Receita Líquida':     'Receita Líquida',
        '(-) Custos/Despesas': 'Custos & Despesas',
        'EBITDA':              'EBITDA',
        'Lucro Líquido':       'Lucro Líquido',
    }
    for linha in dre:
        nome = label_map.get(linha.get('linha'))
        if not nome: continue
        val = linha.get('valor_atual')
        qoq = linha.get('variacao_qoq'); yoy = linha.get('variacao_yoy')
        text_at(c, nome, L_X + 18, cy, 8.5, SLATE_100, 'Helvetica')
        text_at(c, money(abs(val) if val is not None else None), L_X + 175, cy, 9, WHITE, 'Helvetica-Bold')
        if qoq is not None:
            text_at(c, f'{pct(qoq)} {delta_arrow(qoq)}', L_X + L_W - 105, cy, 7.5, delta_color(qoq), 'Helvetica-Bold', 'right')
        else:
            text_at(c, '—', L_X + L_W - 105, cy, 7.5, SLATE_500, 'Helvetica', 'right')
        if yoy is not None:
            text_at(c, f'{pct(yoy)} {delta_arrow(yoy)}', L_X + L_W - 18, cy, 7.5, delta_color(yoy), 'Helvetica-Bold', 'right')
        else:
            text_at(c, '—', L_X + L_W - 18, cy, 7.5, SLATE_500, 'Helvetica', 'right')
        cy -= 22

    # ── BOX 3: INDICADORES OPERACIONAIS ─────────────────────────────────────
    rect(c, L_X, IND_Y, L_W, IND_H)
    cy = section_title(c, 'Indicadores Operacionais', L_X, IND_Y + IND_H, L_W)

    ind = data.get('indicadores_operacionais', {}) or {}
    conv = ind.get('conversao_media_rede')
    tick = ind.get('ticket_medio_rede')
    pc = ind.get('unidade_critica_conversao') or {}
    pt = ind.get('unidade_ticket_abaixo') or {}

    cy -= 8
    text_at(c, 'Conversão:', L_X + 18, cy, 9, SLATE_300, 'Helvetica-Bold')
    text_at(c, pct_plain(conv) if conv is not None else 'n/d', L_X + 110, cy, 10, WHITE, 'Helvetica-Bold')
    text_at(c, '▼', L_X + 158, cy, 8, RED, 'Helvetica-Bold')
    if pc.get('unidade'):
        text_at(c, f'{pc["unidade"]}: {pct_plain(pc.get("valor"))}', L_X + 175, cy, 8, SLATE_200)

    cy -= 22
    text_at(c, 'Ticket Médio:', L_X + 18, cy, 9, SLATE_300, 'Helvetica-Bold')
    text_at(c, money(tick) if tick is not None else 'n/d', L_X + 110, cy, 10, WHITE, 'Helvetica-Bold')
    text_at(c, '▼', L_X + 175, cy, 8, AMBER, 'Helvetica-Bold')
    if pt.get('unidade'):
        text_at(c, f'{pt["unidade"]}: {money(pt.get("valor"))}', L_X + 192, cy, 8, SLATE_200)

    # ── BOX 4: ALERTAS E AÇÕES ──────────────────────────────────────────────
    rect(c, R_X, ALT_Y, R_W, ALT_H)
    cy = section_title(c, 'Alertas e Ações', R_X, ALT_Y + ALT_H, R_W)

    # right sub-panel "Unidades a avaliar"
    SUB_W = 130
    SUB_X = R_X + R_W - SUB_W - 10
    SUB_Y = ALT_Y + 12
    SUB_H = ALT_H - 38
    rect(c, SUB_X, SUB_Y, SUB_W, SUB_H, r=6, fill=PANEL_BG2, stroke=BORDER_SOFT, sw=0.4)
    text_at(c, 'UNIDADES A AVALIAR', SUB_X + 10, SUB_Y + SUB_H - 14, 7, SLATE_300, 'Helvetica-Bold')
    text_at(c, 'PARA FECHAMENTO',    SUB_X + 10, SUB_Y + SUB_H - 24, 7, SLATE_300, 'Helvetica-Bold')
    avaliacao = data.get('alertas', {}).get('avaliacao_fechamento', []) or []
    uy = SUB_Y + SUB_H - 42
    for av in avaliacao[:6]:
        text_at(c, '›', SUB_X + 14, uy, 10, CYAN, 'Helvetica-Bold')
        text_at(c, av.get('unidade', ''), SUB_X + 26, uy, 9, WHITE, 'Helvetica')
        uy -= 18

    # alert cards (left side of the panel)
    CARD_W = R_W - SUB_W - 26
    CARD_X = R_X + 10
    nivel_cfg = {
        'critico':  (RED_BG,   RED,   RED),
        'atencao':  (AMBER_BG, AMBER, AMBER),
        'positivo': (GREEN_DIM, GREEN, GREEN),
    }
    items = (data.get('alertas', {}).get('items', []) or [])[:3]
    cy -= 4
    PILL_W, PILL_H = 82, 18
    for alert in items:
        nivel = alert.get('nivel', 'atencao')
        bg, brd, txt_col = nivel_cfg.get(nivel, (PANEL_BG2, CYAN, CYAN))
        card_h = 56
        card_y = cy - card_h
        if card_y < ALT_Y + 10:
            break
        rect(c, CARD_X, card_y, CARD_W, card_h, r=6, fill=bg, stroke=brd, sw=0.7)

        # text zone left of the pill — keep all alert text inside this zone
        TEXT_W = CARD_W - PILL_W - 26  # bullet+padding before, pill+padding after
        TEXT_X = CARD_X + 26
        # rough char widths: 4.7pt @ 8.5 bold, 4.0pt @ 7.5 normal
        max_title_chars = max(10, int(TEXT_W / 4.7))
        max_det_chars   = max(10, int(TEXT_W / 4.0))

        # bullet + title
        filled_circle(c, CARD_X + 14, card_y + card_h - 16, 4.5, brd)
        titulo = (alert.get('titulo') or '').upper()
        if len(titulo) > max_title_chars:
            titulo = titulo[:max_title_chars - 1] + '…'
        text_at(c, titulo, TEXT_X, card_y + card_h - 19, 8.5, txt_col, 'Helvetica-Bold')

        # detalhe (1-2 lines, also bounded to TEXT_W)
        det = alert.get('detalhe') or ''
        line1 = det[:max_det_chars]
        line2 = det[max_det_chars:max_det_chars * 2]
        text_at(c, line1, CARD_X + 14, card_y + card_h - 33, 7.5, SLATE_100)
        if line2:
            text_at(c, line2, CARD_X + 14, card_y + card_h - 44, 7.5, SLATE_100)

        # right pill "Dados Confiáveis"
        px = CARD_X + CARD_W - PILL_W - 8
        py = card_y + (card_h - PILL_H) / 2
        pill(c, px, py, PILL_W, PILL_H, PANEL_BG2, brd)
        text_at(c, 'Dados Confiáveis', px + PILL_W / 2, py + 6, 7, SLATE_100, 'Helvetica-Bold', 'center')

        cy = card_y - 7

    # ── BOX 5+6: RANKING + PIPELINE (side by side) ──────────────────────────
    RKP_GAP = 7
    RANK_W = (R_W * 0.62) - RKP_GAP / 2
    PIPE_W = (R_W * 0.38) - RKP_GAP / 2
    RANK_X = R_X
    PIPE_X = RANK_X + RANK_W + RKP_GAP

    # RANKING
    rect(c, RANK_X, RKP_Y, RANK_W, RKP_H)
    cy = section_title(c, 'Ranking de Unidades', RANK_X, RKP_Y + RKP_H, RANK_W)

    col_w = (RANK_W - 24) / 2
    # header pills for top/bottom
    pill_h2 = 16
    py = cy - pill_h2 - 2
    pill(c, RANK_X + 10, py, col_w, pill_h2, GREEN_DIM, GREEN)
    pill(c, RANK_X + 14 + col_w, py, col_w, pill_h2, RED_DIM, RED)
    text_at(c, 'TOP 5 EBITDA', RANK_X + 10 + col_w / 2, py + 5, 7.5, GREEN, 'Helvetica-Bold', 'center')
    text_at(c, 'BOTTOM 5 EBITDA', RANK_X + 14 + col_w + col_w / 2, py + 5, 7.5, RED, 'Helvetica-Bold', 'center')
    cy = py - 4

    ranking = data.get('ranking', {}) or {}
    top5 = ranking.get('top_5', []) or []
    bot5 = ranking.get('bottom_5', []) or []
    n = min(5, max(len(top5), len(bot5)))
    cy -= 10
    for i in range(n):
        if i < len(top5):
            t = top5[i]
            text_at(c, f'{i+1}. {t.get("unidade","")}', RANK_X + 14, cy, 7.5, WHITE, 'Helvetica-Bold')
            text_at(c, money_k(t.get('valor')), RANK_X + 10 + col_w - 6, cy, 7.5, GREEN, 'Helvetica-Bold', 'right')
        if i < len(bot5):
            b = bot5[i]
            bv = b.get('valor', 0) or 0
            text_at(c, f'{i+1}. {b.get("unidade","")}', RANK_X + 18 + col_w, cy, 7.5, WHITE, 'Helvetica-Bold')
            txt = f'-R$ {abs(bv)/1000:,.0f}k'.replace(',', '.') if bv < 0 else money_k(bv)
            text_at(c, txt, RANK_X + 14 + 2*col_w - 6, cy, 7.5, RED if bv < 0 else SLATE_100, 'Helvetica-Bold', 'right')
        cy -= 13

    # PIPELINE
    rect(c, PIPE_X, RKP_Y, PIPE_W, RKP_H)
    cy = section_title(c, 'Pipeline Financeiro', PIPE_X, RKP_Y + RKP_H, PIPE_W)

    pip = data.get('pipeline_financeiro', {}) or {}
    leads = pip.get('leads_ativos')
    cir   = pip.get('cirurgias_esperadas')
    pot   = pip.get('potencial_receita')

    leads_str = f'{int(leads):,}'.replace(',', '.') if leads is not None else 'n/d'
    cir_str   = f'{int(cir):,}'.replace(',', '.') if cir   is not None else 'n/d'
    pot_str   = money_mm(pot) if pot is not None else 'n/d'

    cy -= 10
    items = [
        ('Leads Ativos:',          leads_str),
        ('Cirurgias Agendadas:',   cir_str),
        ('Potencial de Receita:',  pot_str),
    ]
    for lbl, val in items:
        text_at(c, lbl, PIPE_X + 12, cy, 8.5, SLATE_200)
        text_at(c, val, PIPE_X + PIPE_W - 12, cy, 9, WHITE, 'Helvetica-Bold', 'right')
        cy -= 22

    # ── BOX 7: QUALIDADE DE DADOS ───────────────────────────────────────────
    rect(c, R_X, QUA_Y, R_W, QUA_H, fill=AMBER_BG, stroke=AMBER, sw=0.7)
    cy_q = QUA_Y + QUA_H / 2 - 3
    text_at(c, '!  QUALIDADE DE DADOS', R_X + 14, cy_q, 9, AMBER, 'Helvetica-Bold')
    qual = data.get('qualidade_dados', {}) or {}
    flags = (qual.get('flags') or []) + (qual.get('observacoes') or [])
    if flags:
        text_at(c, f'▼  {flags[0][:60]}', R_X + 200, cy_q, 8.5, SLATE_100, 'Helvetica-Bold')
    else:
        text_at(c, '✓  Sem inconsistências detectadas', R_X + 200, cy_q, 8.5, GREEN, 'Helvetica-Bold')

    # ── footer ──────────────────────────────────────────────────────────────
    gerado = dt.datetime.now().strftime('%d/%m/%Y %H:%M')
    text_at(c, f'ICB · Executive Finance Control · Uso interno · Confidencial · Gerado em {gerado}', M, 6, 6, SLATE_500)
    text_at(c, 'Página 1 de 1', PW - M, 6, 6, SLATE_500, 'Helvetica', 'right')

    c.save()
    return buf.getvalue()
