import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

const paramsFromFilters = (filters) => {
  const p = {};
  ['anos', 'meses', 'competencias', 'unidades', 'profissionais'].forEach((k) => {
    if (filters?.[k]?.length) p[k] = filters[k];
  });
  return p;
};

export const getDashboardBundle = async (filters = {}) => {
  const params = paramsFromFilters(filters);
  const [last, summary, unidades, profissionais, financeiro, fiscal, alertas, unidadesStatus] = await Promise.all([
    api.get('/last-update'),
    api.get('/dashboard/summary', { params }),
    api.get('/dashboard/unidades', { params }),
    api.get('/dashboard/profissionais', { params }),
    api.get('/dashboard/financeiro', { params }),
    api.get('/dashboard/fiscal', { params }),
    api.get('/dashboard/alertas', { params }),
    api.get('/unidades/status'),
  ]);

  const alertasPayload = alertas.data;
  const alertasLegacy = Array.isArray(alertasPayload) ? alertasPayload : (alertasPayload?.alertas || []);

  return {
    lastUpdate: last.data,
    summary: summary.data,
    unidades: unidades.data,
    profissionais: profissionais.data,
    financeiro: financeiro.data,
    fiscal: fiscal.data,
    alertas: alertasLegacy,
    alertasStructured: Array.isArray(alertasPayload) ? null : alertasPayload,
    unidadesStatus: unidadesStatus.data,
  };
};

export const getFilterOptions = async () => {
  const res = await api.get('/dashboard/options');
  return res.data;
};

// ────────────────────────────────────────────────────────────────────────────
// Carrega e remodela todos os dados para o App.jsx (Resumo/Unidades/Médicos/Financeiro/Alertas).
// Retorna o objeto DATA esperado pelo App.
// ────────────────────────────────────────────────────────────────────────────
const MES_LABELS = ['JAN','FEV','MAR','ABR','MAI','JUN','JUL','AGO','SET','OUT','NOV','DEZ'];

const safeNum = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const ratio = (n, d) => (d ? n / d : null);

const buildSaude = ({ ll, mg_ll, conv, ticket, statusUnidade }) => {
  if (statusUnidade === 'encerrada' || statusUnidade === 'em_reestruturacao') return 'critico';
  if (ll == null) return 'atencao';
  if (ll < 0) return 'critico';
  if ((mg_ll != null && mg_ll < 0.10) || (conv != null && conv < 0.35)) return 'atencao';
  return 'ok';
};

export const getDashboardForApp = async (periodo = 'trimestre') => {
  // 1ª fase: dados independentes do período (precisamos da série para descobrir last/tri).
  const [last, summary, profissionais, financeiro, alertas, statusRes] = await Promise.all([
    api.get('/last-update'),
    api.get('/dashboard/summary'),
    api.get('/dashboard/profissionais'),
    api.get('/dashboard/financeiro'),
    api.get('/dashboard/alertas'),
    api.get('/unidades/status'),
  ]);

  const serie = financeiro.data?.serie || [];
  const serieByComp = serie.reduce((acc, s) => { acc[s.competencia] = s; return acc; }, {});

  // últimas 3 competências = trimestre corrente
  const tri = serie.slice(-3);
  const lastComp = tri[tri.length - 1];
  const lastCompKey = lastComp?.competencia;

  // 2ª fase: dados por unidade filtrados pelo período escolhido (mês ou trimestre).
  const triKeys = tri.map((s) => s.competencia);
  const compFilter = periodo === 'mes' && lastCompKey ? [lastCompKey] : triKeys;
  const unitParams = compFilter.length ? { competencias: compFilter } : {};
  const unitParamsSerializer = { paramsSerializer: { indexes: null } };

  const [unidades, unidadesFinTri] = await Promise.all([
    api.get('/dashboard/unidades', { params: unitParams, ...unitParamsSerializer }),
    api.get('/dashboard/unidades-financeiro', { params: unitParams, ...unitParamsSerializer }),
  ]);
  const [lastYear, lastMonth] = (lastCompKey || '').split('-').map(Number);
  const labelMonth = lastMonth ? `${MES_LABELS[lastMonth - 1]}/${String(lastYear).slice(-2)}` : '—';

  // Mesmo mês ano anterior
  const prevYearKey = lastYear && lastMonth ? `${lastYear - 1}-${String(lastMonth).padStart(2, '0')}` : null;
  const prevYearMonth = prevYearKey ? serieByComp[prevYearKey] : null;
  const prevLabel = prevYearKey && lastMonth ? `${MES_LABELS[lastMonth - 1]}/${String(lastYear - 1).slice(-2)}` : '—';

  // Q (trimestre) anterior: mesmas 3 competências do tri corrente, shiftadas -12 meses.
  const triPrevKeys = tri.map((s) => {
    const [yy, mm] = s.competencia.split('-').map(Number);
    return `${yy - 1}-${String(mm).padStart(2, '0')}`;
  });
  const triPrev = triPrevKeys.map((k) => serieByComp[k]).filter(Boolean);

  const sum = (arr, k) => arr.reduce((a, b) => a + (b?.[k] || 0), 0);

  const lastMonthData = lastComp ? {
    label: labelMonth,
    rb: lastComp.receita_bruta,
    rl: lastComp.receita_liquida,
    ebitda: lastComp.ebitda,
    ll: lastComp.lucro_liquido,
    mg_ebitda: ratio(lastComp.ebitda, lastComp.receita_bruta),
    mg_ll: ratio(lastComp.lucro_liquido, lastComp.receita_bruta),
  } : { label: '—', rb: 0, rl: 0, ebitda: 0, ll: 0, mg_ebitda: null, mg_ll: null };

  const prevMonthData = {
    label: prevLabel,
    rb: prevYearMonth?.receita_bruta ?? null,
    ll: prevYearMonth?.lucro_liquido ?? null,
    mg_ll: prevYearMonth ? ratio(prevYearMonth.lucro_liquido, prevYearMonth.receita_bruta) : null,
  };

  const triRb = sum(tri, 'receita_bruta');
  const triRl = sum(tri, 'receita_liquida');
  const triEb = sum(tri, 'ebitda');
  const triLl = sum(tri, 'lucro_liquido');

  const triPrevRb = sum(triPrev, 'receita_bruta');
  const triLabel = lastComp ? `Q${Math.ceil(lastMonth / 3)} ${lastYear}` : '—';
  const triPrevLabel = lastYear ? `Q${Math.ceil(lastMonth / 3)} ${lastYear - 1}` : '—';

  // Per-unit financials (trimestre = mesmas filters; backend já agrega)
  const finByUnit = (unidadesFinTri.data || []).reduce((acc, u) => { acc[u.unidade] = u; return acc; }, {});
  const opByUnit = (unidades.data || []).reduce((acc, u) => { acc[u.unidade] = u; return acc; }, {});
  const statusByUnit = (statusRes.data?.items || []).reduce((acc, s) => { acc[s.unidade] = s.status; return acc; }, {});

  const allUnitNames = new Set([...Object.keys(finByUnit), ...Object.keys(opByUnit)]);
  const unidadesArr = [...allUnitNames].map((nome) => {
    const f = finByUnit[nome] || {};
    const o = opByUnit[nome] || {};
    const status = statusByUnit[nome];
    if (status === 'encerrada') return null;
    const rb = safeNum(f.receita_bruta) ?? safeNum(o.receita_operacional) ?? 0;
    const ll = safeNum(f.lucro_liquido);
    const ebitda = safeNum(f.ebitda);
    const conv = safeNum(o.conv_consulta_cirurgia);
    const ticket = safeNum(o.ticket_medio_cirurgia);
    const cirurgias = safeNum(o.cirurgias);
    return {
      UNIDADE: nome,
      rb,
      ll,
      ebitda,
      mg_ll: ll != null && rb ? ll / rb : null,
      mg_ebitda: ebitda != null && rb ? ebitda / rb : null,
      conv,
      ticket,
      cirurgias,
      periodo,
      saude: buildSaude({ ll, mg_ll: ll != null && rb ? ll / rb : null, conv, ticket, statusUnidade: status }),
    };
  }).filter(Boolean).sort((a, b) => (b.ll ?? -Infinity) - (a.ll ?? -Infinity));

  const top5 = unidadesArr.slice(0, 5);
  const bot5 = unidadesArr.slice(-5).reverse();

  // Profissionais
  const profissionaisArr = (profissionais.data || []).map((p) => {
    const consultas = safeNum(p.consultas_totais) || 0;
    const cirurgias = safeNum(p.cirurgias) || 0;
    return {
      nome: p.profissional,
      unidade: p.unidade,
      cirurgias,
      consultas,
      conv: consultas > 0 ? cirurgias / consultas : 0,
    };
  }).sort((a, b) => b.cirurgias - a.cirurgias);

  // Meses do trimestre
  const meses = tri.map((s) => {
    const [, m] = s.competencia.split('-').map(Number);
    return {
      mes: m,
      label: MES_LABELS[m - 1],
      rb: s.receita_bruta,
      ebitda: s.ebitda,
      ll: s.lucro_liquido,
      mg_ebitda: ratio(s.ebitda, s.receita_bruta),
      mg_ll: ratio(s.lucro_liquido, s.receita_bruta),
    };
  });

  // Alertas (já vêm prontos do backend)
  const alertasPayload = alertas.data;
  const alertasItems = Array.isArray(alertasPayload)
    ? alertasPayload
    : (alertasPayload?.items || alertasPayload?.alertas || []);
  const alertasNorm = alertasItems.map((a) => ({
    nivel: a.nivel || 'info',
    titulo: a.titulo || '',
    detalhe: a.detalhe || '',
    unidades: a.unidades || [],
    acao: a.acao || (a.categoria === 'fiscal' ? 'Acionar financeiro antes do fechamento.' :
                    a.categoria === 'operacional' ? 'Investigar funil de captação e protocolo.' :
                    a.categoria === 'prejuizo' ? 'Avaliar estrutura de custos ou encerramento.' : ''),
  }));

  const statusSummary = statusRes.data?.summary || {};

  return {
    ultimo_mes: lastMonthData,
    mesmo_mes_ano_anterior: prevMonthData,
    yoy_mes: prevMonthData.rb ? (lastMonthData.rb - prevMonthData.rb) / prevMonthData.rb : null,
    q1: {
      label: triLabel,
      rb: triRb, rl: triRl, ebitda: triEb, ll: triLl,
      mg_ebitda: triRb ? triEb / triRb : null,
      mg_ll: triRb ? triLl / triRb : null,
    },
    q1_ano_anterior: { label: triPrevLabel, rb: triPrev.length ? triPrevRb : null },
    yoy_q1: triPrevRb ? (triRb - triPrevRb) / triPrevRb : null,
    meses,
    top5,
    bot5,
    unidades: unidadesArr,
    alertas: alertasNorm,
    profissionais: profissionaisArr,
    saude_rede: (statusSummary.ativa || 0) - (statusSummary.em_reestruturacao || 0) > 15 ? 'Estável' : 'Em observação',
    unidades_ativas: statusSummary.ativa || unidadesArr.length,
    unidades_encerradas: statusSummary.encerrada || 0,
    conv_media_rede: summary.data?.funil?.conv_consulta_cirurgia || null,
    fiscal_pct_nf: summary.data?.fiscal?.percentual_nf || null,
    last_update: last.data?.last_update,
    status_dados: last.data?.status,
  };
};

export const getExecutiveReport = async (filters = {}) => {
  const params = paramsFromFilters(filters);
  if (filters.periodo) params.periodo = filters.periodo;
  const res = await api.get('/dashboard/executive-report', { params });
  return res.data;
};
