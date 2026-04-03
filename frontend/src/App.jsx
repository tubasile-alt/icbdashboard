import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import KpiCard from './components/KpiCard';
import UpdateBadge from './components/UpdateBadge';
import { getDashboard } from './lib/api';

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const NIVEL_CONFIG = {
  critico: {
    border: 'border-red-500/80',
    bg: 'bg-red-500/10',
    dot: 'bg-red-500',
    badge: 'bg-red-500/20 text-red-300',
    label: 'CRÍTICO',
  },
  atencao: {
    border: 'border-amber-500/80',
    bg: 'bg-amber-500/10',
    dot: 'bg-amber-500',
    badge: 'bg-amber-500/20 text-amber-300',
    label: 'ATENÇÃO',
  },
  info: {
    border: 'border-indigo-500/80',
    bg: 'bg-indigo-500/10',
    dot: 'bg-indigo-500',
    badge: 'bg-indigo-500/20 text-indigo-300',
    label: 'INFO',
  },
};
const CATEGORIA_LABEL = { financeiro: 'Financeiro', operacional: 'Operacional', fiscal: 'Fiscal' };

export default function App() {
  const [data, setData] = useState(null);
  const [mostrarTodosAlertas, setMostrarTodosAlertas] = useState(false);
  const [alertasExpandidos, setAlertasExpandidos] = useState({});

  useEffect(() => {
    const fetch = async () => {
      const payload = await getDashboard();
      setData(payload);
    };
    fetch();
    const id = setInterval(fetch, 60_000);
    return () => clearInterval(id);
  }, []);

  const kpis = useMemo(() => {
    if (!data) return [];
    const s = data.summary;
    return [
      { title: 'Receita total (base operacional)', value: money.format(s.receita_total || 0) },
      { title: 'EBITDA (financeiro)', value: money.format(s.ebitda || 0) },
      { title: 'Lucro líquido (financeiro)', value: money.format(s.lucro_liquido || 0) },
      { title: 'Cirurgias', value: (s.cirurgias || 0).toLocaleString('pt-BR') },
      { title: 'Ticket médio', value: money.format(s.ticket_medio || 0) },
    ];
  }, [data]);

  const alertas = data?.alertas || [];
  const criticos = alertas.filter((a) => a.nivel === 'critico').length;
  const atencoes = alertas.filter((a) => a.nivel === 'atencao').length;
  const alertasVisiveis = mostrarTodosAlertas ? alertas : alertas.slice(0, 4);

  if (!data) {
    return <div className="min-h-screen bg-slateDeep p-6 text-slate-100">Carregando dashboard...</div>;
  }

  return (
    <div className="min-h-screen bg-slateDeep px-6 py-8 text-slate-100">
      <header className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-3xl font-semibold">ICB Performance Dashboard</h1>
          <p className="text-sm text-slate-400">Visão executiva operacional e financeira</p>
        </div>
        <UpdateBadge status={data.status} lastUpdate={data.last_update} />
      </header>

      <section className="grid gap-4 md:grid-cols-5">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.title} title={kpi.title} value={kpi.value} />
        ))}
      </section>

      <section className="mt-6 overflow-hidden rounded-xl border border-slate-700/70 glass">
        <div className="flex items-center justify-between border-b border-slate-700/70 bg-slate-950/30 px-4 py-3">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-semibold">Alertas Executivos</h3>
            <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-semibold text-red-300">{criticos} críticos</span>
            <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-semibold text-amber-300">{atencoes} atenções</span>
          </div>
          <span className="text-xs text-slate-400">{alertas.length} alertas no total</span>
        </div>

        <div className="divide-y divide-slate-800/80">
          {alertasVisiveis.map((alerta, idx) => {
            const key = `${idx}-${alerta.titulo}`;
            const isOpen = !!alertasExpandidos[key];
            const cfg = NIVEL_CONFIG[alerta.nivel] || NIVEL_CONFIG.info;
            return (
              <div key={key} className={`border-l-4 ${cfg.border} ${cfg.bg}`}>
                <button
                  className="flex w-full items-center gap-3 px-4 py-3 text-left"
                  onClick={() => setAlertasExpandidos((prev) => ({ ...prev, [key]: !prev[key] }))}
                >
                  <span className={`h-2 w-2 shrink-0 rounded-full ${cfg.dot}`} />
                  <span className={`rounded px-2 py-0.5 text-[10px] font-bold tracking-wide ${cfg.badge}`}>{cfg.label}</span>
                  <span className="text-xs text-slate-400">{CATEGORIA_LABEL[alerta.categoria] || alerta.categoria}</span>
                  <span className="flex-1 text-sm text-slate-100">{alerta.titulo}</span>
                  <span className={`text-slate-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}>▾</span>
                </button>
                {isOpen && (
                  <div className="px-10 pb-3">
                    <p className="text-sm text-slate-300">{alerta.detalhe}</p>
                    {!!alerta.unidades?.length && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {alerta.unidades.map((u) => (
                          <span key={u} className="rounded border border-slate-700 bg-slate-800/70 px-2 py-0.5 text-xs text-slate-300">
                            {u}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {alertas.length > 4 && (
          <button
            className="w-full border-t border-slate-700/70 px-4 py-2 text-xs text-slate-400 hover:bg-slate-900/40"
            onClick={() => setMostrarTodosAlertas((v) => !v)}
          >
            {mostrarTodosAlertas ? '▲ Mostrar menos' : `▼ Ver mais ${alertas.length - 4} alertas`}
          </button>
        )}
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="glass rounded-xl p-4 lg:col-span-1">
          <h3 className="mb-3 text-sm font-semibold">Receita por mês (base operacional)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={data.receita_por_mes}>
              <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
              <XAxis dataKey="competencia" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip />
              <Line dataKey="receita" stroke="#22d3ee" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="glass rounded-xl p-4 lg:col-span-1">
          <h3 className="mb-3 text-sm font-semibold">Cirurgias por mês</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={data.cirurgias_por_mes}>
              <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
              <XAxis dataKey="competencia" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip />
              <Line dataKey="cirurgias" stroke="#a78bfa" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="glass rounded-xl p-4 lg:col-span-1">
          <h3 className="mb-3 text-sm font-semibold">Receita por unidade (base operacional)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.receita_por_unidade}>
              <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
              <XAxis dataKey="unidade" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip />
              <Bar dataKey="receita" fill="#14b8a6" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="mt-6 glass rounded-xl p-4">
        <h3 className="mb-4 text-sm font-semibold">Tabela de unidades</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="pb-2">Unidade</th>
                <th className="pb-2">Receita</th>
                <th className="pb-2">Cirurgias</th>
                <th className="pb-2">Ticket médio</th>
                <th className="pb-2">Eficiência</th>
              </tr>
            </thead>
            <tbody>
              {data.unidades.map((u) => (
                <tr key={u.unidade} className="border-t border-slate-700/60">
                  <td className="py-2">{u.unidade}</td>
                  <td className="py-2">{money.format(u.receita)}</td>
                  <td className="py-2">{u.cirurgias.toLocaleString('pt-BR')}</td>
                  <td className="py-2">{money.format(u.ticket_medio)}</td>
                  <td className="py-2">{u.eficiencia.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
