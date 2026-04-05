import { useMemo, useState } from 'react';

const R = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `R$ ${Math.abs(Number(value)).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
};

const Pct = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${(Number(value) * 100).toFixed(1)}%`;
};

const colorValue = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '#6b7280';
  return Number(value) >= 0 ? '#34d399' : '#f87171';
};

const monthLabel = (competencia) => {
  const map = {
    '01': 'JAN',
    '02': 'FEV',
    '03': 'MAR',
    '04': 'ABR',
    '05': 'MAI',
    '06': 'JUN',
    '07': 'JUL',
    '08': 'AGO',
    '09': 'SET',
    '10': 'OUT',
    '11': 'NOV',
    '12': 'DEZ',
  };

  if (!competencia) return '—';
  const [, month] = String(competencia).split('-');
  return map[month] || String(competencia);
};

const styles = {
  panel: { background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 12, overflow: 'hidden', marginTop: 16 },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.2)', flexWrap: 'wrap', gap: 8 },
  headerTitle: { fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.4)' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.22)', marginLeft: 10 },
  tabs: { display: 'flex', gap: 4 },
  tab: (active) => ({ padding: '4px 12px', borderRadius: 6, fontSize: 11, fontWeight: 500, border: 'none', cursor: 'pointer', background: active ? 'rgba(255,255,255,0.1)' : 'transparent', color: active ? '#fff' : 'rgba(255,255,255,0.35)', transition: 'all 0.15s' }),
  kpiGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', borderBottom: '1px solid rgba(255,255,255,0.06)' },
  kpiCell: { padding: '12px 14px', borderRight: '1px solid rgba(255,255,255,0.05)' },
  kpiLabel: { fontSize: 10, color: 'rgba(255,255,255,0.32)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' },
  kpiValue: (color) => ({ fontSize: 13, fontWeight: 700, color }),
  body: { padding: 16 },
  wfRow: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 },
  wfLabel: { width: 150, fontSize: 11, color: 'rgba(255,255,255,0.5)', textAlign: 'right', flexShrink: 0, lineHeight: 1.3 },
  wfBarWrap: { flex: 1, height: 26, position: 'relative', display: 'flex', alignItems: 'center' },
  wfBar: (color, width) => ({ height: '100%', width, borderRadius: 4, background: color, minWidth: 4 }),
  wfVal: (color) => ({ width: 130, fontSize: 11, fontWeight: 600, textAlign: 'right', flexShrink: 0, color }),
  wfMg: { width: 48, fontSize: 10, color: 'rgba(255,255,255,0.25)', textAlign: 'right', flexShrink: 0 },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: { padding: '8px 10px', fontSize: 10, fontWeight: 600, textAlign: 'left', color: 'rgba(255,255,255,0.35)', borderBottom: '1px solid rgba(255,255,255,0.08)', whiteSpace: 'nowrap', textTransform: 'uppercase', letterSpacing: '0.05em' },
  thClick: (active) => ({ padding: '8px 10px', fontSize: 10, fontWeight: 600, textAlign: 'right', color: active ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.3)', borderBottom: '1px solid rgba(255,255,255,0.08)', whiteSpace: 'nowrap', cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.05em' }),
  td: { padding: '8px 10px', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.6)' },
  tdName: { padding: '8px 10px', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.8)', fontWeight: 500, whiteSpace: 'nowrap' },
  tdNum: (color) => ({ padding: '8px 10px', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)', color, fontWeight: 600, textAlign: 'right' }),
  tdRight: { padding: '8px 10px', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.4)', textAlign: 'right' },
  note: { fontSize: 10, color: 'rgba(255,255,255,0.2)', marginTop: 12, lineHeight: 1.6 },
};

export default function FinancialDreCard({ summaryFinanceiro, financeiroSerie, unidades }) {
  const [tab, setTab] = useState('waterfall');
  const [sortField, setSortField] = useState('ll');

  const dre = useMemo(() => {
    const receitaBruta = Number(summaryFinanceiro?.receita_bruta || 0);
    const receitaLiquida = Number(summaryFinanceiro?.receita_liquida || 0);
    const ebitda = Number(summaryFinanceiro?.ebitda || 0);
    const ll = Number(summaryFinanceiro?.lucro_liquido || 0);
    const margemEbitda = summaryFinanceiro?.margem_ebitda ?? null;
    const margemLl = summaryFinanceiro?.margem_liquida ?? null;

    const issPisCofins = receitaBruta - receitaLiquida;
    const custosDespesas = receitaLiquida - ebitda;
    const irpjCsll = ebitda - ll;

    return {
      ytd: {
        receita_bruta: receitaBruta,
        receita_liquida: receitaLiquida,
        ebitda,
        margem_ebitda: margemEbitda,
        ll,
        margem_ll: margemLl,
      },
      meses: (financeiroSerie || []).map((m) => ({
        mes_label: monthLabel(m.competencia),
        receita_bruta: null,
        ebitda: m.ebitda ?? null,
        ll: m.lucro_liquido ?? null,
        margem_ebitda: null,
        margem_ll: null,
      })),
      por_unidade: (unidades || []).map((u) => ({
        unidade: u.unidade,
        receita_bruta: u.receita_operacional ?? null,
        ebitda: null,
        ll: null,
        margem_ebitda: null,
        margem_ll: null,
        participacao_receita: receitaBruta > 0 ? (u.receita_operacional || 0) / receitaBruta : null,
      })),
      waterfall: [
        { label: 'Receita Bruta', valor: receitaBruta, tipo: 'total' },
        { label: '(-) ISS/PIS/COFINS', valor: -Math.max(issPisCofins, 0), tipo: 'negativo' },
        { label: '= Receita Líquida', valor: receitaLiquida, tipo: 'total' },
        { label: '(-) Custos/Despesas', valor: -Math.max(custosDespesas, 0), tipo: 'negativo' },
        { label: '= EBITDA', valor: ebitda, tipo: 'total' },
        { label: '(-) IRPJ/CSLL', valor: -Math.max(irpjCsll, 0), tipo: 'negativo' },
        { label: '= Lucro Líquido', valor: ll, tipo: 'total' },
      ],
    };
  }, [financeiroSerie, summaryFinanceiro, unidades]);

  const kpis = [
    { label: 'Receita Bruta', val: R(dre.ytd.receita_bruta), color: 'rgba(255,255,255,0.8)' },
    { label: 'Receita Líquida', val: R(dre.ytd.receita_liquida), color: 'rgba(255,255,255,0.8)' },
    { label: 'EBITDA', val: R(dre.ytd.ebitda), color: colorValue(dre.ytd.ebitda) },
    { label: 'Mg. EBITDA', val: Pct(dre.ytd.margem_ebitda), color: colorValue(dre.ytd.margem_ebitda) },
    { label: 'Lucro Líquido', val: R(dre.ytd.ll), color: colorValue(dre.ytd.ll) },
    { label: 'Mg. LL', val: Pct(dre.ytd.margem_ll), color: colorValue(dre.ytd.margem_ll) },
  ];

  const maxWf = Math.max(...dre.waterfall.map((i) => Math.abs(i.valor)), 1);
  const sortedUnits = [...dre.por_unidade].sort((a, b) => {
    const va = a[sortField] ?? -Infinity;
    const vb = b[sortField] ?? -Infinity;
    return vb - va;
  });

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <div>
          <span style={styles.headerTitle}>Demonstração de Resultado</span>
          <span style={styles.headerSub}>Acumulado dos filtros selecionados</span>
        </div>
        <div style={styles.tabs}>
          {[
            ['waterfall', 'Cascata'],
            ['mensal', 'Mensal'],
            ['unidades', 'Por Unidade'],
          ].map(([id, label]) => (
            <button key={id} type="button" style={styles.tab(tab === id)} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div style={styles.kpiGrid}>
        {kpis.map((kpi) => (
          <div key={kpi.label} style={styles.kpiCell}>
            <div style={styles.kpiLabel}>{kpi.label}</div>
            <div style={styles.kpiValue(kpi.color)}>{kpi.val}</div>
          </div>
        ))}
      </div>

      <div style={styles.body}>
        {tab === 'waterfall' && (
          <div>
            {dre.waterfall.map((item) => {
              const isTotal = item.tipo === 'total';
              const isNeg = item.valor < 0;
              const barPct = Math.abs(item.valor) / maxWf;
              const barColor = isTotal ? 'rgba(99,102,241,0.45)' : isNeg ? 'rgba(239,68,68,0.3)' : 'rgba(52,211,153,0.3)';
              const textColor = isTotal ? '#a5b4fc' : isNeg ? '#f87171' : '#34d399';
              const valStr = item.valor === 0 ? '—' : `${isNeg ? '- ' : ''}${R(Math.abs(item.valor))}`;

              let mg = null;
              if (item.label === '= EBITDA') mg = Pct(dre.ytd.margem_ebitda);
              if (item.label === '= Lucro Líquido') mg = Pct(dre.ytd.margem_ll);

              return (
                <div key={item.label} style={styles.wfRow}>
                  <div style={styles.wfLabel}>{item.label}</div>
                  <div style={styles.wfBarWrap}>
                    <div style={styles.wfBar(barColor, item.valor === 0 ? '4px' : `${Math.max(barPct * 100, 1)}%`)} />
                  </div>
                  <div style={styles.wfVal(textColor)}>{valStr}</div>
                  <div style={styles.wfMg}>{mg || ''}</div>
                </div>
              );
            })}
            <p style={styles.note}>* Custos e impostos estimados com base na diferença entre agregados financeiros disponíveis.</p>
          </div>
        )}

        {tab === 'mensal' && (
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Mês</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>Receita Bruta</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>EBITDA</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>Mg. EBITDA</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>Lucro Líquido</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>Mg. LL</th>
                </tr>
              </thead>
              <tbody>
                {dre.meses.map((m) => (
                  <tr key={m.mes_label}>
                    <td style={{ ...styles.td, color: 'rgba(255,255,255,0.8)', fontWeight: 600 }}>{m.mes_label}</td>
                    <td style={styles.tdRight}>{R(m.receita_bruta)}</td>
                    <td style={styles.tdNum(colorValue(m.ebitda))}>{R(m.ebitda)}</td>
                    <td style={styles.tdNum(colorValue(m.margem_ebitda))}>{Pct(m.margem_ebitda)}</td>
                    <td style={styles.tdNum(colorValue(m.ll))}>{R(m.ll)}</td>
                    <td style={styles.tdNum(colorValue(m.margem_ll))}>{Pct(m.margem_ll)}</td>
                  </tr>
                ))}
                <tr style={{ borderTop: '1px solid rgba(255,255,255,0.12)' }}>
                  <td style={{ ...styles.td, color: 'rgba(255,255,255,0.9)', fontWeight: 700 }}>YTD</td>
                  <td style={{ ...styles.tdRight, color: 'rgba(255,255,255,0.8)', fontWeight: 700 }}>{R(dre.ytd.receita_bruta)}</td>
                  <td style={{ ...styles.tdNum(colorValue(dre.ytd.ebitda)), fontWeight: 700 }}>{R(dre.ytd.ebitda)}</td>
                  <td style={{ ...styles.tdNum(colorValue(dre.ytd.margem_ebitda)), fontWeight: 700 }}>{Pct(dre.ytd.margem_ebitda)}</td>
                  <td style={{ ...styles.tdNum(colorValue(dre.ytd.ll)), fontWeight: 700 }}>{R(dre.ytd.ll)}</td>
                  <td style={{ ...styles.tdNum(colorValue(dre.ytd.margem_ll)), fontWeight: 700 }}>{Pct(dre.ytd.margem_ll)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {tab === 'unidades' && (
          <div style={{ overflowX: 'auto' }}>
            <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginBottom: 10 }}>Clique no cabeçalho para ordenar.</p>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Unidade</th>
                  {[
                    ['receita_bruta', 'Rec. Bruta'],
                    ['ebitda', 'EBITDA'],
                    ['margem_ebitda', 'Mg. EBITDA'],
                    ['ll', 'Lucro Líq.'],
                    ['margem_ll', 'Mg. LL'],
                    ['participacao_receita', 'Part. %'],
                  ].map(([field, label]) => (
                    <th key={field} style={styles.thClick(sortField === field)} onClick={() => setSortField(field)}>
                      {label} {sortField === field ? '↓' : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedUnits.map((u) => (
                  <tr key={u.unidade}>
                    <td style={styles.tdName}>{u.unidade}</td>
                    <td style={styles.tdRight}>{R(u.receita_bruta)}</td>
                    <td style={styles.tdNum(colorValue(u.ebitda))}>{R(u.ebitda)}</td>
                    <td style={styles.tdNum(colorValue(u.margem_ebitda))}>{Pct(u.margem_ebitda)}</td>
                    <td style={styles.tdNum(colorValue(u.ll))}>{R(u.ll)}</td>
                    <td style={styles.tdNum(colorValue(u.margem_ll))}>{Pct(u.margem_ll)}</td>
                    <td style={styles.tdRight}>{Pct(u.participacao_receita)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
