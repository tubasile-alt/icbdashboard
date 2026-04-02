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

export default function App() {
  const [data, setData] = useState(null);

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
