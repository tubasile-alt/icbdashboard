const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const FILTER_KEYS = ['anos', 'meses', 'competencias', 'unidades', 'profissionais'];

function toQuery(filters = {}) {
  const qp = new URLSearchParams();
  FILTER_KEYS.forEach((key) => {
    const values = Array.isArray(filters[key]) ? filters[key] : [];
    values.filter(Boolean).forEach((value) => qp.append(key, value));
  });
  return qp.toString();
}

export default function ReportButton({ filters = {} }) {
  const query = toQuery(filters);
  const href = `${API_URL}/export/executive-report-pdf${query ? `?${query}` : ''}`;

  return (
    <a
      href={href}
      className="flex items-center gap-2 rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-300 transition-all duration-150 hover:border-indigo-400/60 hover:bg-indigo-500/20 whitespace-nowrap"
    >
      <span>⬇</span>
      <span>Exportar PDF</span>
    </a>
  );
}
