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

export const getDashboardForApp = async (periodo = 'trimestre', selecao = {}) => {
  // 1ª fase: dados independentes do período (precisamos da série para descobrir defaults).
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

  // Defaults: usamos a última competência fechada disponível.
  const lastInSerie = serie[serie.length - 1];
  const [defaultYear, defaultMonth] = (lastInSerie?.competencia || '').split('-').map(Number);
  const anoCorrente = defaultYear || new Date().getFullYear();
  const mesMaxCorrente = (defaultYear === anoCorrente && defaultMonth) ? defaultMonth : 12;

  // Resolve mês e trimestre efetivos a partir da seleção do usuário.
  const ano = selecao.ano || anoCorrente;
  const mesSelecionado = periodo === 'mes'
    ? (selecao.mes || defaultMonth || 1)
    : null;
  const triSelecionado = periodo === 'trimestre'
    ? (selecao.tri || (defaultMonth ? Math.ceil(defaultMonth / 3) : 1))
    : null;
  const triReferencia = triSelecionado || (mesSelecionado ? Math.ceil(mesSelecionado / 3) : 1);
  const mesReferencia = mesSelecionado || triReferencia * 3;

  // Competências-alvo
  const pad = (n) => String(n).padStart(2, '0');
  const triMonths = [triReferencia * 3 - 2, triReferencia * 3 - 1, triReferencia * 3];
  const triKeys = triMonths.map((m) => `${ano}-${pad(m)}`);
  const monthKey = `${ano}-${pad(mesReferencia)}`;
  const compFilter = periodo === 'mes' ? [monthKey] : triKeys;

  const unitParams = { competencias: compFilter };
  const unitParamsSerializer = { paramsSerializer: { indexes: null } };
  const [unidades, unidadesFinTri] = await Promise.all([
    api.get('/dashboard/unidades', { params: unitParams, ...unitParamsSerializer }),
    api.get('/dashboard/unidades-financeiro', { params: unitParams, ...unitParamsSerializer }),
  ]);

  const labelMonth = `${MES_LABELS[mesReferencia - 1]}/${String(ano).slice(-2)}`;
  const selComp = serieByComp[monthKey];

  // Mesmo mês ano anterior
  const prevYearKey = `${ano - 1}-${pad(mesReferencia)}`;
  const prevYearMonth = serieByComp[prevYearKey];
  const prevLabel = `${MES_LABELS[mesReferencia - 1]}/${String(ano - 1).slice(-2)}`;

  // Trimestre selecionado e anterior (-12 meses)
  const triData = triKeys.map((k) => serieByComp[k]).filter(Boolean);
  const triPrevKeys = triKeys.map((k) => {
    const [yy, mm] = k.split('-').map(Number);
    return `${yy - 1}-${pad(mm)}`;
  });
  const triPrev = triPrevKeys.map((k) => serieByComp[k]).filter(Boolean);

  const sum = (arr, k) => arr.reduce((a, b) => a + (b?.[k] || 0), 0);

  const lastMonthData = selComp ? {
    label: labelMonth,
    rb: selComp.receita_bruta,
    rl: selComp.receita_liquida,
    ebitda: selComp.ebitda,
    ll: selComp.lucro_liquido,
    mg_ebitda: ratio(selComp.ebitda, selComp.receita_bruta),
    mg_ll: ratio(selComp.lucro_liquido, selComp.receita_bruta),
  } : { label: labelMonth, rb: null, rl: null, ebitda: null, ll: null, mg_ebitda: null, mg_ll: null, sem_dado: true };

  const prevMonthData = {
    label: prevLabel,
    rb: prevYearMonth?.receita_bruta ?? null,
    ll: prevYearMonth?.lucro_liquido ?? null,
    mg_ll: prevYearMonth ? ratio(prevYearMonth.lucro_liquido, prevYearMonth.receita_bruta) : null,
  };

  const triRb = sum(triData, 'receita_bruta');
  const triRl = sum(triData, 'receita_liquida');
  const triEb = sum(triData, 'ebitda');
  const triLl = sum(triData, 'lucro_liquido');

  const triPrevRb = sum(triPrev, 'receita_bruta');
  const triLabel = `Q${triReferencia} ${ano}`;
  const triPrevLabel = `Q${triReferencia} ${ano - 1}`;

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

  // Meses do trimestre selecionado (preenchendo zeros quando ainda não fechado)
  const meses = triKeys.map((k) => {
    const [, m] = k.split('-').map(Number);
    const s = serieByComp[k];
    if (!s) return { mes: m, label: MES_LABELS[m - 1], rb: 0, ebitda: 0, ll: 0, mg_ebitda: null, mg_ll: null };
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
    selecao: {
      periodo,
      ano,
      mes: mesReferencia,
      tri: triReferencia,
      ano_corrente: anoCorrente,
      mes_max_corrente: mesMaxCorrente,
    },
  };
};

// Recarrega os números de UMA unidade no período escolhido (mês ou trimestre do ano corrente).
// Retorna { rb, ll, ebitda, mg_ll, mg_ebitda, conv, ticket, cirurgias, periodo, saude, mes, tri, ano }.
export const getUnitDetail = async (unidade, periodo = 'trimestre', selecao = {}) => {
  const pad = (n) => String(n).padStart(2, '0');
  const ano = selecao.ano;
  const mes = selecao.mes;
  const tri = selecao.tri;
  if (!ano) throw new Error('Ano é obrigatório para getUnitDetail');

  const triRef = periodo === 'trimestre' ? tri : Math.ceil(mes / 3);
  const triKeys = [triRef * 3 - 2, triRef * 3 - 1, triRef * 3].map((m) => `${ano}-${pad(m)}`);
  const monthKey = `${ano}-${pad(mes || triRef * 3)}`;
  const compFilter = periodo === 'mes' ? [monthKey] : triKeys;

  const params = { competencias: compFilter, unidades: [unidade] };
  const cfg = { params, paramsSerializer: { indexes: null } };

  const [opRes, finRes, statusRes] = await Promise.all([
    api.get('/dashboard/unidades', cfg),
    api.get('/dashboard/unidades-financeiro', cfg),
    api.get('/unidades/status'),
  ]);

  const o = (opRes.data || []).find((u) => u.unidade === unidade) || {};
  const f = (finRes.data || []).find((u) => u.unidade === unidade) || {};
  const status = (statusRes.data?.items || []).find((s) => s.unidade === unidade)?.status;

  const rb = safeNum(f.receita_bruta) ?? safeNum(o.receita_operacional) ?? 0;
  const ll = safeNum(f.lucro_liquido);
  const ebitda = safeNum(f.ebitda);
  const conv = safeNum(o.conv_consulta_cirurgia);
  const ticket = safeNum(o.ticket_medio_cirurgia);
  const cirurgias = safeNum(o.cirurgias);
  const mg_ll = ll != null && rb ? ll / rb : null;
  const mg_ebitda = ebitda != null && rb ? ebitda / rb : null;

  return {
    UNIDADE: unidade,
    rb, ll, ebitda, mg_ll, mg_ebitda, conv, ticket, cirurgias,
    periodo,
    ano,
    mes: mes || null,
    tri: triRef,
    saude: buildSaude({ ll, mg_ll, conv, ticket, statusUnidade: status }),
  };
};

export const getExecutiveReport = async (filters = {}) => {
  const params = paramsFromFilters(filters);
  if (filters.periodo) params.periodo = filters.periodo;
  const res = await api.get('/dashboard/executive-report', { params });
  return res.data;
};
