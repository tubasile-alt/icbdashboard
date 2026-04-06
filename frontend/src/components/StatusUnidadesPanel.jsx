import { useMemo, useState } from 'react';

const STATUS_ORDER = {
  ativa: 1,
  em_reestruturacao: 2,
  suspensa: 3,
  encerrada: 4,
};

const STATUS_CONFIG = {
  ativa: {
    label: 'Ativa',
    color: '#34d399',
    bg: 'rgba(52,211,153,0.1)',
    border: 'rgba(52,211,153,0.25)',
  },
  em_reestruturacao: {
    label: 'Em reestruturação',
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.1)',
    border: 'rgba(245,158,11,0.25)',
  },
  suspensa: {
    label: 'Suspensa',
    color: '#a78bfa',
    bg: 'rgba(167,139,250,0.1)',
    border: 'rgba(167,139,250,0.25)',
  },
  encerrada: {
    label: 'Encerrada',
    color: '#f87171',
    bg: 'rgba(239,68,68,0.08)',
    border: 'rgba(239,68,68,0.2)',
  },
};

const MONTHS_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const formatMonthYear = (value) => {
  if (!value) return '—';
  const [year, month] = String(value).split('-');
  const monthIdx = Number(month) - 1;
  if (!year || Number.isNaN(monthIdx) || monthIdx < 0 || monthIdx > 11) return '—';
  return `${MONTHS_PT[monthIdx]}/${year}`;
};

const truncateText = (value, max = 55) => {
  if (!value) return '—';
  if (value.length <= max) return value;
  return `${value.slice(0, max).trim()}…`;
};

export default function StatusUnidadesPanel({ data }) {
  const [activeFilter, setActiveFilter] = useState(null);
  const [expandedRows, setExpandedRows] = useState({});

  const items = data?.items || [];

  const filteredItems = useMemo(() => {
    const base = [...items].sort((a, b) => {
      const pa = STATUS_ORDER[a.status] || 99;
      const pb = STATUS_ORDER[b.status] || 99;
      if (pa !== pb) return pa - pb;
      return (a.unidade || '').localeCompare(b.unidade || '', 'pt-BR');
    });

    if (!activeFilter) return base;
    return base.filter((row) => row.status === activeFilter);
  }, [items, activeFilter]);

  const timeline = data?.timeline || [];

  const toggleRow = (key) => {
    setExpandedRows((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const onSelectStatus = (status) => {
    setActiveFilter((prev) => (prev === status ? null : status));
  };

  return (
    <section className="mt-6 glass rounded-2xl p-4 md:p-6">
      <div className="mb-4">
        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">ICB PERFORMANCE DASHBOARD</p>
        <h2 className="mt-1 text-2xl font-semibold text-slate-100">Status de Unidades</h2>
        <p className="mt-1 text-sm text-slate-400">
          Unidades encerradas são excluídas das médias de conversão, margem e benchmarks
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(STATUS_CONFIG).map(([status, config]) => {
          const total = data?.summary?.[status] || 0;
          const selected = activeFilter === status;
          return (
            <button
              key={status}
              type="button"
              onClick={() => onSelectStatus(status)}
              className="rounded-xl border p-4 text-left transition"
              style={{
                backgroundColor: config.bg,
                borderColor: selected ? config.color : config.border,
                boxShadow: selected ? `0 0 0 1px ${config.color}` : 'none',
              }}
            >
              <p className="text-xs uppercase tracking-wide text-slate-300">{config.label}</p>
              <p className="mt-2 text-3xl font-semibold" style={{ color: config.color }}>{total}</p>
            </button>
          );
        })}
      </div>

      <div className="mt-4 rounded-xl border border-cyan-500/25 bg-cyan-500/5 p-4">
        <p className="text-sm font-semibold text-cyan-200">Correção de viés</p>
        <p className="mt-2 text-sm text-slate-300">
          Correção de viés: as unidades encerradas são automaticamente excluídas das médias de conversão, margem e benchmarks da rede.
          Os dados históricos continuam visíveis para análise de tendência.
        </p>
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-700/70 bg-slate-950/20">
        <table className="min-w-full text-left">
          <thead>
            <tr className="border-b border-slate-700 text-xs uppercase tracking-wide text-slate-400">
              <th className="px-3 py-2">Unidade</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Fechamento</th>
              <th className="px-3 py-2">Nas médias</th>
              <th className="px-3 py-2">Motivo</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((row) => {
              const rowKey = `${row.unidade}-${row.status}`;
              const expanded = Boolean(expandedRows[rowKey]);
              const statusConfig = STATUS_CONFIG[row.status] || { label: row.status, color: '#94a3b8' };
              const motivo = row.motivo || '—';
              return (
                <tr
                  key={rowKey}
                  onClick={() => row.motivo && toggleRow(rowKey)}
                  className={`border-b border-slate-800/70 last:border-b-0 ${row.motivo ? 'cursor-pointer hover:bg-slate-900/50' : ''}`}
                >
                  <td className="whitespace-nowrap px-3 py-2 text-sm text-slate-100">{row.unidade || '—'}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-sm">
                    <span className="rounded-full px-2 py-1 text-xs" style={{ color: statusConfig.color, backgroundColor: `${statusConfig.color}20` }}>
                      {statusConfig.label}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-sm text-slate-200">{formatMonthYear(row.data_encerramento)}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-sm text-slate-200">{row.excluir_de_medias ? 'Não' : 'Sim'}</td>
                  <td className="px-3 py-2 text-sm text-slate-300">{expanded ? motivo : truncateText(motivo)}</td>
                </tr>
              );
            })}
            {filteredItems.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-sm text-slate-400">Nenhuma unidade para o filtro selecionado.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-5 rounded-xl border border-slate-700/70 bg-slate-950/25 p-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-200">Timeline de Fechamentos</h3>
        <div className="mt-3 space-y-3">
          {timeline.map((item, idx) => (
            <div key={`${item.unidade}-${item.status}-${idx}`} className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-3">
              <p className="text-sm font-semibold text-slate-100">
                {item.unidade} {' '}
                <span className="text-xs font-normal text-slate-400">
                  {item.tipo === 'status_incerto' ? 'Status incerto' : formatMonthYear(item.data_encerramento)}
                </span>
              </p>
              <p className="mt-1 text-sm text-slate-300">{item.motivo || '—'}</p>
            </div>
          ))}
          {timeline.length === 0 && <p className="text-sm text-slate-400">Nenhum fechamento registrado.</p>}
        </div>
      </div>

      <div className="mt-4 text-xs text-slate-400">
        <p>Datas de fechamento inferidas da planilha — confirmar com gestão antes de publicar.</p>
        <p className="mt-1">Campo editável via PATCH /unidades/status/:unidade no backend.</p>
      </div>
    </section>
  );
}
