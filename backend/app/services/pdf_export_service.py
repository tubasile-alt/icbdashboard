import datetime as dt
from html import escape
from urllib.parse import urlencode

from pyppeteer import launch


FILTER_KEYS = ('anos', 'meses', 'competencias', 'unidades', 'profissionais')


def _build_period_label(filters: dict) -> str:
    competencias = filters.get('competencias') or []
    meses = filters.get('meses') or []
    anos = filters.get('anos') or []

    if competencias:
        if len(competencias) == 1:
            return competencias[0]
        return f'{competencias[0]} a {competencias[-1]}'

    if meses and anos:
        return f"{', '.join(str(m) for m in meses)} / {', '.join(str(a) for a in anos)}"

    if anos:
        return ', '.join(str(a) for a in anos)

    return 'Últimos dados disponíveis'


def _build_export_url(frontend_base_url: str, filters: dict) -> str:
    qp = [('export', 'true')]
    for key in FILTER_KEYS:
        values = filters.get(key) or []
        for value in values:
            qp.append((key, str(value)))

    return f"{frontend_base_url.rstrip('/')}/executive-report?{urlencode(qp, doseq=True)}"


def _header_template(periodo: str, status_dados: str, gerado_em: str) -> str:
    return f"""
    <div style="
        width:100%;
        font-size:9px;
        color:#cbd5e1;
        padding:0 10mm;
        display:flex;
        justify-content:space-between;
        align-items:center;
        border-bottom:1px solid rgba(148,163,184,0.35);
    ">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-weight:700;color:#93c5fd;">ICB</span>
        <span>Relatório Executivo</span>
      </div>
      <div>Período: {escape(periodo)} · Status: {escape(status_dados)} · Gerado em: {escape(gerado_em)}</div>
    </div>
    """


def _footer_template(gerado_em: str) -> str:
    return f"""
    <div style="
        width:100%;
        font-size:8px;
        color:#94a3b8;
        padding:0 10mm;
        display:flex;
        justify-content:space-between;
        align-items:center;
        border-top:1px solid rgba(148,163,184,0.35);
    ">
      <div>Uso interno · Confidencial</div>
      <div>{escape(gerado_em)} · Página <span class="pageNumber"></span>/<span class="totalPages"></span></div>
    </div>
    """


async def generate_executive_report_pdf(frontend_base_url: str, filters: dict, status_dados: str, timeout_ms: int = 120000) -> bytes:
    periodo = _build_period_label(filters)
    gerado_em = dt.datetime.now().strftime('%d/%m/%Y %H:%M')
    url = _build_export_url(frontend_base_url, filters)

    browser = await launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    )

    try:
        page = await browser.newPage()
        await page.setViewport({'width': 1600, 'height': 1100, 'deviceScaleFactor': 2, 'isMobile': False})
        await page.goto(url, {'waitUntil': 'networkidle0', 'timeout': timeout_ms})
        await page.waitForSelector('[data-executive-report-root="true"]', {'timeout': timeout_ms})
        await page.evaluate("""
          async () => {
            if (document.fonts && document.fonts.ready) {
              await document.fonts.ready;
            }
          }
        """)

        await page.emulateMedia('screen')

        return await page.pdf(
            {
                'landscape': True,
                'printBackground': True,
                'preferCSSPageSize': True,
                'displayHeaderFooter': True,
                'headerTemplate': _header_template(periodo, status_dados, gerado_em),
                'footerTemplate': _footer_template(gerado_em),
                'margin': {'top': '14mm', 'right': '8mm', 'bottom': '14mm', 'left': '8mm'},
            }
        )
    finally:
        await browser.close()
