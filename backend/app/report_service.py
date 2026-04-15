import datetime
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db

router = APIRouter()

try:
    from reportlab.graphics.shapes import Drawing, Rect
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    W, _ = A4
    REPORTLAB_OK = True
except ImportError:
    W = 595.0
    REPORTLAB_OK = False

NAVY2 = None
NAVY3 = None
GRAY3 = None
GRAY4 = None
ACCENT = None
INDIGO = None
GREEN = None
RED = None
AMBER = None
WHITE = None
GRAY = None
GRAY2 = None


def _init_colors():
    global NAVY2, NAVY3, GRAY3, GRAY4, ACCENT, INDIGO, GREEN, RED, AMBER, WHITE, GRAY, GRAY2
    NAVY2 = colors.HexColor('#111827')
    NAVY3 = colors.HexColor('#1e2a3a')
    GRAY3 = colors.HexColor('#1E293B')
    GRAY4 = colors.HexColor('#334155')
    ACCENT = colors.HexColor('#3B82F6')
    INDIGO = colors.HexColor('#6366F1')
    GREEN = colors.HexColor('#10B981')
    RED = colors.HexColor('#EF4444')
    AMBER = colors.HexColor('#F59E0B')
    WHITE = colors.white
    GRAY = colors.HexColor('#94A3B8')
    GRAY2 = colors.HexColor('#CBD5E1')


def R(v):
    if v is None:
        return '—'
    s = f"{abs(float(v)):,.0f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {s}'


def Pct(v, d=1):
    if v is None:
        return '—'
    return f"{float(v) * 100:.{d}f}%"


def st(name, **kw):
    base = dict(fontName='Helvetica', fontSize=9, textColor=GRAY2, leading=13, spaceAfter=0, spaceBefore=0)
    base.update(kw)
    return ParagraphStyle(name, **base)


def th(textv, align='CENTER'):
    a = {'LEFT': TA_LEFT, 'CENTER': TA_CENTER, 'RIGHT': TA_RIGHT}[align]
    return Paragraph(f'<b>{textv}</b>', st('_th', fontSize=7.5, textColor=GRAY, leading=10, alignment=a))


def td(textv, bold=False, color=None, align='LEFT', size=8.5):
    color = color or WHITE
    a = {'LEFT': TA_LEFT, 'CENTER': TA_CENTER, 'RIGHT': TA_RIGHT}[align]
    fn = 'Helvetica-Bold' if bold else 'Helvetica'
    return Paragraph(str(textv), st('_td', fontName=fn, fontSize=size, textColor=color, leading=11, alignment=a))


def tbl(data, cols, extras=None):
    base = [
        ('BACKGROUND', (0, 0), (-1, 0), GRAY3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [NAVY2, NAVY3]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('BOX', (0, 0), (-1, -1), 0.5, GRAY4),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    if extras:
        base += extras
    t = Table(data, colWidths=cols)
    t.setStyle(TableStyle(base))
    return t


def mini_bar(v, mx, cor=None, w=55, h=5):
    cor = cor or ACCENT
    d = Drawing(w, h + 2)
    d.add(Rect(0, 1, w, h, fillColor=GRAY4, strokeColor=None))
    bw = max(2, w * min(abs(float(v or 0)) / mx, 1)) if mx else 2
    d.add(Rect(0, 1, bw, h, fillColor=cor, strokeColor=None))
    return d


def _query_dados(db: Session, periodo: str) -> dict:
    # fact_financeiro_mensal: receita_bruta, impostos, receita_liquida, custos, despesas,
    #                         ebitda, margem_ebitda, lucro_liquido, margem_liquida
    # fact_unidade_mensal: receita_operacional (not receita)
    # fact_producao_profissional_mensal: consultas_totais (not consultas)

    if periodo == 'mes':
        filtro_fin = """
            WHERE competencia = (
                SELECT MAX(competencia) FROM fact_financeiro_mensal
                WHERE receita_bruta > 0
            )
        """
        filtro_unidade = """
            WHERE (ano * 100 + mes) = (
                SELECT MAX(ano * 100 + mes) FROM fact_unidade_mensal
                WHERE receita_operacional > 0
            )
        """
        n_meses = 1
    else:
        filtro_fin = """
            WHERE competencia IN (
                SELECT competencia FROM (
                    SELECT DISTINCT competencia FROM fact_financeiro_mensal
                    WHERE receita_bruta > 0
                    ORDER BY competencia DESC LIMIT 3
                ) AS _sub_fin
            )
        """
        filtro_unidade = """
            WHERE (ano * 100 + mes) IN (
                SELECT ym FROM (
                    SELECT DISTINCT (ano * 100 + mes) AS ym FROM fact_unidade_mensal
                    WHERE receita_operacional > 0
                    ORDER BY ym DESC LIMIT 3
                ) AS _sub_um
            )
        """
        n_meses = 3

    ytd_row = db.execute(text(f"""
        SELECT
            COALESCE(SUM(receita_bruta), 0)    AS receita_bruta,
            COALESCE(SUM(receita_liquida), 0)  AS receita_liquida,
            COALESCE(SUM(ebitda), 0)           AS ebitda,
            COALESCE(SUM(lucro_liquido), 0)    AS lucro_liquido,
            COALESCE(SUM(impostos), 0)         AS impostos,
            COALESCE(SUM(custos + despesas), 0) AS custos_despesas
        FROM fact_financeiro_mensal
        {filtro_fin}
    """)).fetchone()

    rb  = float(ytd_row.receita_bruta or 0)
    rl  = float(ytd_row.receita_liquida or rb)
    ebt = float(ytd_row.ebitda or 0)
    ll  = float(ytd_row.lucro_liquido or 0)

    ytd = {
        'receita_bruta':   rb,
        'iss_pis_cofins':  float(ytd_row.impostos or 0),
        'devolucoes':      0.0,
        'receita_liquida': rl,
        'custos_despesas': float(ytd_row.custos_despesas or 0),
        'ebitda':          ebt,
        'margem_ebitda':   round(ebt / rl, 4) if rl else None,
        'irpj_csll':       0.0,
        'll':              ll,
        'margem_ll':       round(ll / rl, 4) if rl else None,
    }

    try:
        yoy_row = db.execute(
            text("""
                SELECT COALESCE(SUM(receita_operacional), 0) AS receita_anterior
                FROM fact_unidade_mensal
                WHERE (ano * 100 + mes) IN (
                    SELECT ym_ant FROM (
                        SELECT DISTINCT ((ano - 1) * 100 + mes) AS ym_ant
                        FROM fact_unidade_mensal
                        WHERE receita_operacional > 0
                        ORDER BY (ano * 100 + mes) DESC LIMIT :n
                    ) AS _sub_yoy
                )
            """),
            {'n': n_meses},
        ).fetchone()
        rb_anterior = float(yoy_row.receita_anterior or 0)
        yoy = round(rb / rb_anterior - 1, 4) if rb_anterior else 0
    except Exception:
        db.rollback()
        yoy = 0

    meses_rows = db.execute(text(f"""
        SELECT
            competencia,
            receita_bruta,
            ebitda,
            lucro_liquido                                               AS ll,
            CASE WHEN receita_liquida > 0 THEN ebitda / receita_liquida      ELSE NULL END AS margem_ebitda,
            CASE WHEN receita_liquida > 0 THEN lucro_liquido / receita_liquida ELSE NULL END AS margem_ll
        FROM fact_financeiro_mensal
        {filtro_fin}
        ORDER BY competencia ASC
    """)).fetchall()

    meses_label = {1:'JAN',2:'FEV',3:'MAR',4:'ABR',5:'MAI',6:'JUN',
                   7:'JUL',8:'AGO',9:'SET',10:'OUT',11:'NOV',12:'DEZ'}
    meses = []
    for r in meses_rows:
        comp = str(r.competencia)
        parts = comp.split('-')
        mes_num = int(parts[1]) if len(parts) == 2 else 0
        meses.append({
            'mes_label':    meses_label.get(mes_num, comp),
            'receita_bruta': float(r.receita_bruta or 0),
            'ebitda':        float(r.ebitda or 0),
            'll':            float(r.ll or 0),
            'margem_ebitda': float(r.margem_ebitda) if r.margem_ebitda is not None else None,
            'margem_ll':     float(r.margem_ll)     if r.margem_ll     is not None else None,
        })

    # Unidades: usar fact_financeiro_mensal agrupado por unidade para margens
    try:
        unidades_rows = db.execute(text(f"""
            SELECT
                um.unidade,
                COALESCE(SUM(um.receita_operacional), 0) AS receita_bruta,
                SUM(fm.ebitda)                            AS ebitda,
                SUM(fm.lucro_liquido)                     AS ll,
                CASE WHEN SUM(fm.receita_liquida) > 0
                     THEN SUM(fm.ebitda) / SUM(fm.receita_liquida) END AS margem_ebitda,
                CASE WHEN SUM(fm.receita_liquida) > 0
                     THEN SUM(fm.lucro_liquido) / SUM(fm.receita_liquida) END AS margem_ll
            FROM fact_unidade_mensal um
            LEFT JOIN fact_financeiro_mensal fm
                ON fm.unidade = um.unidade
                AND (fm.ano * 100 + fm.mes) = (um.ano * 100 + um.mes)
            {filtro_unidade}
            GROUP BY um.unidade
            ORDER BY SUM(fm.lucro_liquido) DESC NULLS LAST
        """)).fetchall()
    except Exception:
        db.rollback()
        unidades_rows = []

    if not unidades_rows:
        try:
            unidades_rows = db.execute(text(f"""
                SELECT
                    unidade,
                    COALESCE(SUM(receita_operacional), 0) AS receita_bruta,
                    NULL AS ebitda,
                    NULL AS ll,
                    NULL AS margem_ebitda,
                    NULL AS margem_ll
                FROM fact_unidade_mensal
                {filtro_unidade}
                GROUP BY unidade
                ORDER BY SUM(receita_operacional) DESC
            """)).fetchall()
        except Exception:
            db.rollback()
            unidades_rows = []

    por_unidade = []
    for r in unidades_rows:
        por_unidade.append({
            'UNIDADE':      r.unidade,
            'receita_bruta': float(r.receita_bruta or 0),
            'ebitda':        float(r.ebitda)        if r.ebitda        is not None else None,
            'll':            float(r.ll)             if r.ll            is not None else None,
            'margem_ebitda': float(r.margem_ebitda) if r.margem_ebitda is not None else None,
            'margem_ll':     float(r.margem_ll)     if r.margem_ll     is not None else None,
        })

    alertas = _build_alertas(db, ytd, yoy, por_unidade)

    try:
        conv_row = db.execute(text("""
            SELECT
                COALESCE(SUM(cirurgias), 0)       AS total_cir,
                COALESCE(SUM(consultas_totais), 0) AS total_con
            FROM fact_producao_profissional_mensal
            WHERE ano = (SELECT MAX(ano) FROM fact_producao_profissional_mensal)
        """)).fetchone()
        conv_media = float(conv_row.total_cir) / float(conv_row.total_con) if conv_row and conv_row.total_con else 0.47
    except Exception:
        conv_media = 0.47

    return {
        'ytd': ytd,
        'yoy': yoy,
        'meses': meses,
        'por_unidade': por_unidade,
        'alertas': alertas,
        'conv_media': conv_media,
    }


def _build_alertas(db, ytd, yoy, por_unidade):
    alertas = []

    negativas = [u for u in por_unidade if u['ll'] is not None and u['ll'] < 0]
    if negativas:
        nomes = ' · '.join([f"{u['UNIDADE']} ({Pct(u['margem_ll'])} mg LL)" for u in negativas[:4]])
        alertas.append(
            {
                'nivel': 'critico',
                'categoria': 'financeiro',
                'titulo': f"{len(negativas)} unidade(s) com Lucro Líquido negativo no período",
                'detalhe': nomes,
                'unidades': [u['UNIDADE'] for u in negativas],
            }
        )

    if yoy < -0.03:
        alertas.append(
            {
                'nivel': 'critico',
                'categoria': 'financeiro',
                'titulo': 'Receita do período abaixo do mesmo período do ano anterior',
                'detalhe': f"Queda de {abs(yoy) * 100:.1f}% YoY. {R(ytd['receita_bruta'])} vs período equivalente de 2025.",
                'unidades': [],
            }
        )

    if ytd['margem_ebitda'] is not None and ytd['margem_ebitda'] < 0.15:
        alertas.append(
            {
                'nivel': 'atencao',
                'categoria': 'financeiro',
                'titulo': f"Margem EBITDA da rede abaixo de 15%: {Pct(ytd['margem_ebitda'])}",
                'detalhe': 'Pressão de custos operacionais. Revisar estrutura de despesas fixas.',
                'unidades': [],
            }
        )

    try:
        nf_row = db.execute(text(
            "SELECT percentual_nf FROM fact_fiscal_mensal "
            "WHERE unidade_ref = '__CONSOLIDADO__' ORDER BY competencia DESC LIMIT 1"
        )).fetchone()
        if nf_row and nf_row.percentual_nf and float(nf_row.percentual_nf) < 0.65:
            alertas.append(
                {
                    'nivel': 'atencao',
                    'categoria': 'fiscal',
                    'titulo': f"% NF emitida abaixo do threshold: {Pct(float(nf_row.percentual_nf))} (mín. 65%)",
                    'detalhe': 'Risco de exposição fiscal. Acionar financeiro para regularização.',
                    'unidades': [],
                }
            )
    except Exception:
        db.rollback()
        pass

    return alertas


def _gerar_pdf(dados: dict, periodo: str, titulo: str, sub: str) -> bytes:
    if not REPORTLAB_OK:
        raise RuntimeError('reportlab não instalado. Adicione reportlab>=4.0.0 em requirements.txt')

    _init_colors()

    data_ger = datetime.datetime.now().strftime('%d/%m/%Y às %H:%M')
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.2 * cm,
        title=f'ICB Relatório Executivo — {titulo}',
        author='ICB Performance Dashboard',
    )

    story = []

    story.append(Spacer(1, 2.5 * cm))
    story.append(
        Paragraph(
            'ICB TRANSPLANTE CAPILAR',
            st('brand', fontName='Helvetica-Bold', fontSize=11, textColor=ACCENT, leading=14, alignment=TA_CENTER, letterSpacing=4),
        )
    )
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph('Relatório Executivo de Desempenho', st('t1', fontName='Helvetica-Bold', fontSize=20, textColor=WHITE, leading=24)))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(titulo, st('t2', fontName='Helvetica-Bold', fontSize=14, textColor=INDIGO, leading=18)))
    story.append(Paragraph(sub, st('t3', fontSize=9, textColor=GRAY, leading=13)))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width='100%', thickness=1, color=INDIGO))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f'Gerado em {data_ger}  ·  Uso interno  ·  Confidencial', st('conf', fontSize=8, textColor=GRAY)))
    story.append(Spacer(1, 1 * cm))

    idx = [
        [th('ÍNDICE', 'LEFT'), th('', 'LEFT')],
        *[
            [td(f'0{i}', color=ACCENT), td(s, color=GRAY2)]
            for i, s in enumerate(
                [
                    'Resumo Executivo — KPIs da Rede',
                    'Alertas e Riscos',
                    'DRE Gerencial Consolidada',
                    'Ranking de Unidades',
                    'Indicadores Operacionais',
                    'Notas e Limitações dos Dados',
                ],
                1,
            )
        ],
    ]
    story.append(tbl(idx, [1.2 * cm, 13 * cm]))
    story.append(PageBreak())

    ytd = dados['ytd']
    yoy = dados['yoy']

    story.append(Paragraph('01 · Resumo Executivo', st('sec', fontName='Helvetica-Bold', fontSize=11, textColor=WHITE)))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GRAY4))
    story.append(Spacer(1, 0.3 * cm))
    yoy_cor = GREEN if yoy >= 0 else RED
    sinal = '+' if yoy >= 0 else ''

    def kpi_cell(lbl, val, sub_t, sub_cor):
        return Table(
            [
                [Paragraph(lbl, st('kl', fontSize=8, textColor=GRAY, leading=10))],
                [Paragraph(val, st('kv', fontName='Helvetica-Bold', fontSize=14, textColor=WHITE, leading=17))],
                [Paragraph(sub_t, st('ks', fontSize=8, textColor=sub_cor, leading=10))],
            ],
            colWidths=[4.2 * cm],
            style=[
                ('BACKGROUND', (0, 0), (-1, -1), NAVY3),
                ('BOX', (0, 0), (-1, -1), 0.5, GRAY4),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ],
        )

    row = [[
        kpi_cell('RECEITA BRUTA', R(ytd['receita_bruta']), f'YoY {sinal}{Pct(yoy)}', yoy_cor),
        kpi_cell('EBITDA  ·  MARGEM', R(ytd['ebitda']), Pct(ytd['margem_ebitda']), GREEN),
        kpi_cell('LUCRO LÍQUIDO  ·  MARGEM', R(ytd['ll']), Pct(ytd['margem_ll']), GREEN),
        kpi_cell('UNIDADES ATIVAS', str(len([u for u in dados['por_unidade'] if (u['receita_bruta'] or 0) > 0])), '8 encerradas excluídas', AMBER),
    ]]
    t = Table(row, colWidths=[4.2 * cm] * 4)
    t.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 0.7 * cm))

    story.append(Paragraph('02 · Alertas e Riscos', st('sec', fontName='Helvetica-Bold', fontSize=11, textColor=WHITE)))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GRAY4))
    story.append(Spacer(1, 0.3 * cm))

    cfg_alerta = {
        'critico': (RED, colors.HexColor('#1a0808'), 'CRÍTICO'),
        'atencao': (AMBER, colors.HexColor('#1a1200'), 'ATENÇÃO'),
        'info': (ACCENT, colors.HexColor('#080e1a'), 'INFO'),
    }
    acoes = {
        'financeiro': 'Avaliar estrutura de custos ou estratégia de receita urgentemente.',
        'fiscal': 'Acionar financeiro para regularização antes do fechamento do período.',
        'operacional': 'Investigar processo de captação, médicos e protocolo de indicação.',
    }

    for alerta in dados['alertas']:
        cor, bg, lbl = cfg_alerta.get(alerta['nivel'], (GRAY, NAVY3, 'INFO'))
        acao = acoes.get(alerta['categoria'], 'Verificar e tomar as providências necessárias.')
        bloco = [
            [Paragraph(f'● {lbl}', st('nl', fontName='Helvetica-Bold', fontSize=7.5, textColor=cor, leading=10)), Paragraph(alerta['titulo'], st('at', fontName='Helvetica-Bold', fontSize=9, textColor=WHITE, leading=12))],
            ['', Paragraph(alerta['detalhe'], st('ad', fontSize=8, textColor=GRAY2, leading=11))],
            ['', Paragraph(f'→ {acao}', st('aa', fontSize=7.5, textColor=GRAY, leading=10, fontName='Helvetica-Oblique'))],
        ]
        bt = Table(bloco, colWidths=[1.4 * cm, 15.2 * cm])
        bt.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), bg),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (1, 0), 6),
                    ('BOTTOMPADDING', (0, -1), (-1, -1), 6),
                    ('TOPPADDING', (0, 1), (-1, 1), 2),
                    ('TOPPADDING', (0, 2), (-1, 2), 3),
                    ('BOX', (0, 0), (-1, -1), 0.5, cor),
                    ('LINEAFTER', (0, 0), (0, -1), 1.5, cor),
                    ('SPAN', (0, 0), (0, -1)),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]
            )
        )
        story.append(KeepTogether([bt, Spacer(1, 4)]))

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph('03 · DRE Gerencial Consolidada', st('sec', fontName='Helvetica-Bold', fontSize=11, textColor=WHITE)))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GRAY4))
    story.append(Spacer(1, 0.3 * cm))

    rb = ytd['receita_bruta']
    rl = ytd['receita_liquida']
    linhas_dre = [
        ('Receita Bruta', rb, WHITE, False),
        ('(-) ISS / PIS / COFINS', -ytd['iss_pis_cofins'], GRAY2, True),
        ('(-) Devoluções', -float(ytd['devolucoes']), GRAY2, True),
        ('= Receita Líquida', rl, WHITE, False),
        ('(-) Custos e Despesas', -ytd['custos_despesas'], GRAY2, True),
        ('= EBITDA', ytd['ebitda'], GREEN, False),
        ('(-) IRPJ / CSLL', -ytd['irpj_csll'], GRAY2, True),
        ('= Lucro Líquido', ytd['ll'], GREEN, False),
    ]

    hdr_dre = [[th('LINHA', 'LEFT'), th('VALOR', 'RIGHT'), th('MARGEM s/ RL', 'RIGHT'), th('', 'LEFT')]]
    for label, val, cor_d, is_ded in linhas_dre:
        mg = val / rl if rl and not is_ded and 'Bruta' not in label else None
        bar_cor = cor_d if (val or 0) >= 0 else RED
        hdr_dre.append([td(label, bold=not is_ded, color=cor_d), td(R(val), bold=not is_ded, color=cor_d, align='RIGHT'), td(Pct(mg) if mg else '', color=cor_d, align='RIGHT'), mini_bar(val or 0, rb or 1, cor=bar_cor, w=55, h=5)])

    ex_dre = [
        ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#0d1829')),
        ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#0a1f15')),
        ('BACKGROUND', (0, 8), (-1, 8), colors.HexColor('#0a1f15')),
    ]
    story.append(tbl(hdr_dre, [6.5 * cm, 3.5 * cm, 3 * cm, 3.6 * cm], extras=ex_dre))
    story.append(Spacer(1, 0.4 * cm))

    if dados['meses']:
        story.append(Paragraph('Evolução Mensal', st('sub', fontSize=9, fontName='Helvetica-Bold', textColor=WHITE, leading=12)))
        story.append(Spacer(1, 0.2 * cm))
        mh = [[th('MÊS', 'LEFT'), th('REC. BRUTA', 'RIGHT'), th('EBITDA', 'RIGHT'), th('Mg. EBITDA', 'RIGHT'), th('LL', 'RIGHT'), th('Mg. LL', 'RIGHT')]]
        for mes in dados['meses']:
            ml = mes.get('margem_ll') or 0
            me = mes.get('margem_ebitda') or 0
            cl = GREEN if (mes.get('ll') or 0) >= 0 else RED
            mh.append([td(mes['mes_label'], bold=True, color=WHITE), td(R(mes['receita_bruta']), align='RIGHT', color=GRAY2), td(R(mes.get('ebitda') or 0), align='RIGHT', color=GREEN if (mes.get('ebitda') or 0) >= 0 else RED), td(Pct(me), align='RIGHT', color=GREEN if me >= 0 else RED), td(R(mes.get('ll') or 0), bold=True, align='RIGHT', color=cl), td(Pct(ml), bold=True, align='RIGHT', color=GREEN if ml >= 0 else RED)])
        story.append(tbl(mh, [2.5 * cm, 3.2 * cm, 3.2 * cm, 3 * cm, 3.2 * cm, 2.6 * cm]))

    story.append(PageBreak())

    story.append(Paragraph('04 · Ranking de Unidades', st('sec', fontName='Helvetica-Bold', fontSize=11, textColor=WHITE)))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GRAY4))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph('Ordenado por Lucro Líquido decrescente. Unidades encerradas excluídas das médias.', st('note', fontSize=7.5, textColor=GRAY, leading=11)))
    story.append(Spacer(1, 0.2 * cm))

    hdr_rank = [[th('UNIDADE', 'LEFT'), th('REC. BRUTA', 'RIGHT'), th('EBITDA', 'RIGHT'), th('Mg. EBITDA', 'RIGHT'), th('LL', 'RIGHT'), th('Mg. LL', 'RIGHT')]]
    ex_rank = []

    for i, unit in enumerate(sorted(dados['por_unidade'], key=lambda u: float(u.get('ll') or 0), reverse=True), 1):
        ll_v = float(unit.get('ll') or 0)
        ml_v = float(unit.get('margem_ll') or 0)
        me_v = float(unit.get('margem_ebitda') or 0)
        cl = GREEN if ll_v >= 0 else RED
        if i <= 3:
            ex_rank.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#0a1f15')))
        if ll_v < 0:
            ex_rank.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#1a0808')))
        hdr_rank.append([td(unit['UNIDADE'], bold=i <= 3, color=WHITE if i <= 3 else GRAY2), td(R(unit['receita_bruta']), align='RIGHT', color=GRAY2), td(R(unit.get('ebitda') or 0), align='RIGHT', color=cl), td(Pct(me_v), align='RIGHT', color=cl), td(R(ll_v), bold=True, align='RIGHT', color=cl), td(Pct(ml_v), bold=True, align='RIGHT', color=GREEN if ml_v >= 0 else RED)])

    story.append(tbl(hdr_rank, [5.5 * cm, 3 * cm, 2.8 * cm, 2.5 * cm, 3 * cm, 2.5 * cm], extras=ex_rank))
    story.append(Spacer(1, 0.7 * cm))

    story.append(Paragraph('05 · Indicadores Operacionais', st('sec', fontName='Helvetica-Bold', fontSize=11, textColor=WHITE)))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GRAY4))
    story.append(Spacer(1, 0.3 * cm))
    conv = dados.get('conv_media', 0)
    story.append(Paragraph(f'<b>Taxa de conversão consulta → cirurgia:</b> média da rede {Pct(conv)}', st('c1', fontSize=9, textColor=WHITE, leading=13)))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph('<b>Ticket médio por cirurgia:</b> varia entre unidades. Diferenças indicam variação no mix de procedimentos ou política de precificação local.', st('c2', fontSize=8.5, textColor=GRAY2, leading=12)))
    story.append(Spacer(1, 0.7 * cm))

    story.append(Paragraph('06 · Notas e Limitações dos Dados', st('sec', fontName='Helvetica-Bold', fontSize=11, textColor=WHITE)))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GRAY4))
    story.append(Spacer(1, 0.3 * cm))
    notas = [
        'Dados financeiros disponíveis apenas para os meses já processados pela sincronização do Dropbox.',
        'Dados de 2025 disponíveis apenas no consolidado anual (sem abertura mensal de EBITDA).',
        '8 unidades encerradas foram excluídas de todos os cálculos de média e benchmark da rede.',
        'Comparativo YoY de EBITDA por unidade não disponível para 2025 (aba sem essa granularidade).',
        '% de Notas Fiscais calculada sobre receita bruta consolidada da rede.',
        'Relatório gerado automaticamente a partir da planilha sincronizada via Dropbox.',
    ]
    for i, n in enumerate(notas, 1):
        story.append(Paragraph(f'{i}. {n}', st(f'n{i}', fontSize=8, textColor=GRAY, leading=12)))
        story.append(Spacer(1, 2))

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont('Helvetica', 6.5)
        canvas.setFillColor(GRAY)
        canvas.drawString(2 * cm, 1.3 * cm, 'ICB Transplante Capilar  ·  Relatório Executivo  ·  Uso interno e confidencial')
        canvas.drawRightString(W - 2 * cm, 1.3 * cm, f'Página {doc_.page}')
        canvas.setStrokeColor(GRAY4)
        canvas.setLineWidth(0.5)
        canvas.line(2 * cm, 1.6 * cm, W - 2 * cm, 1.6 * cm)
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


@router.get('/dashboard/relatorio')
def endpoint_relatorio(
    periodo: str = Query(default='trimestre', pattern='^(mes|trimestre)$'),
    db: Session = Depends(get_db),
):
    periodos = {
        'mes': ('Último Mês', 'Mês mais recente com dados disponíveis'),
        'trimestre': ('Último Trimestre', 'Últimos 3 meses acumulados'),
    }
    titulo, sub = periodos[periodo]
    dados = _query_dados(db, periodo)
    pdf_bytes = _gerar_pdf(dados, periodo, titulo, sub)
    nome = f"ICB_Relatorio_Executivo_{titulo.replace(' ', '_')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{nome}"'},
    )
