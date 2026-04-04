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
  const [last, summary, unidades, profissionais, financeiro, fiscal] = await Promise.all([
    api.get('/last-update'),
    api.get('/dashboard/summary', { params }),
    api.get('/dashboard/unidades', { params }),
    api.get('/dashboard/profissionais', { params }),
    api.get('/dashboard/financeiro', { params }),
    api.get('/dashboard/fiscal', { params }),
  ]);

  return {
    lastUpdate: last.data,
    summary: summary.data,
    unidades: unidades.data,
    profissionais: profissionais.data,
    financeiro: financeiro.data,
    fiscal: fiscal.data,
  };
};
