import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Funnel, FunnelChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import KpiCard from './components/KpiCard';
import UpdateBadge from './components/UpdateBadge';
import { getDashboardBundle } from './lib/api';

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const pct = (v) => `${((v || 0) * 100).toFixed(1)}%`;

const SectionTitle = ({ title, subtitle }) => (
  <div className="mb-3 flex items-end justify-between">
    <div>
      <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
      {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
    </div>
  </div>
);

export default function App() {
  const [payload, setPayload] = useState(null);
  const [filters, setFilters] = useState({ anos: [], meses: [], unidades: [], profissionais: [] });

  const fetchData = async () => {
    const data = await getDashboardBundle(filters);
    setPayload(data);
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 60_000);
    return () => clearInterval(id);
  }, [JSON.stringify(filters)]);

  const options = useMemo(() => {
    const anos = new Set();
    const meses = new Set();
    (payload?.financeiro?.serie || []).forEach((x) => {
      const [a, m] = x.competencia.split('-');
      anos.add(Number(a));
      meses.add(Number(m));
    });
    return {
      anos: [...anos].sort(),
      meses: [...meses].sort((a, b) => a - b),
      unidades: [...new Set((payload?.unidades || []).map((u) => u.unidade))],
      profissionais: [...new Set((payload?.profissionais || []).map((p) => p.profissional))],
    };
  }, [payload]);

  if (!payload) return <div className="min-h-screen bg-slateDeep p-6 text-slate-100">Carregando dashboard premium...</div>;

  const s = payload.summary;
  const funnelData = [
    { value: s.funil.leads, name: 'Leads' },
    { value: s.funil.consultas, name: 'Consultas' },
    { value: s.funil.cirurgias, name: 'Cirurgias' },
  ];

  const rankingReceita = [...payload.unidades].sort((a, b) => b.receita_operacional - a.receita_operacional)[0];
  const rankingTicket = [...payload.unidades].sort((a, b) => b.ticket_medio_cirurgia - a.ticket_medio_cirurgia)[0];
  const rankingConv = [...payload.unidades].sort((a, b) => b.conv_consulta_cirurgia - a.conv_consulta_cirurgia)[0];
  const rankingCir = [...payload.unidades].sort((a, b) => b.cirurgias - a.cirurgias)[0];

  return (
    <div className="min-h-screen bg-slateDeep px-6 py-8 text-slate-100">
      <header className="mb-6 grid gap-4 lg:grid-cols-[1fr_360px] lg:items-start">
        <div className="glass rounded-2xl p-6">
          <h1 className="text-3xl font-semibold">ICB Executive Dashboard</h1>
          <p className="mt-2 text-sm text-slate-400">Visão premium com separação operacional, financeira e fiscal.</p>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            {['anos', 'meses', 'unidades', 'profissionais'].map((k) => (
              <select
                key={k}
                className="rounded-xl border border-slate-700/70 bg-slate-900/70 p-3 text-sm outline-none transition focus:border-cyan-400"
                onChange={(e) => setFilters((f) => ({ ...f, [k]: e.target.value ? [e.target.value] : [] }))}
              >
                <option value="">Todos {k}</option>
                {options[k].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            ))}
          </div>
        </div>

        <UpdateBadge status={payload.lastUpdate.status} lastUpdate={payload.lastUpdate.last_update} />
      </header>

      <section>
        <SectionTitle title="Funil Operacional" subtitle="Leads → Consultas → Cirurgias e conversões" />
        <div className="grid gap-4 md:grid-cols-5">
          <KpiCard title="Leads" value={s.funil.leads.toLocaleString('pt-BR')} tooltip="Total de leads." />
          <KpiCard title="Consultas" value={s.funil.consultas.toLocaleString('pt-BR')} tooltip="Consultas totais = presenciais + online." />
          <KpiCard title="Cirurgias" value={s.funil.cirurgias.toLocaleString('pt-BR')} tooltip="Total de cirurgias." />
          <KpiCard title="Conv. Lead → Consulta" value={pct(s.funil.conv_lead_consulta)} tooltip="consultas_totais / leads" />
          <KpiCard title="Conv. Consulta → Cirurgia" value={pct(s.funil.conv_consulta_cirurgia)} tooltip="cirurgias / consultas_totais" />
        </div>
      </section>

      <section className="mt-6">
        <SectionTitle title="Eficiência e Ranking" subtitle="Indicadores de produtividade e comparação entre unidades" />
        <div className="grid gap-4 md:grid-cols-4">
          <KpiCard title="Receita por Lead" value={money.format(s.eficiencia.receita_por_lead)} />
          <KpiCard title="Receita por Consulta" value={money.format(s.eficiencia.receita_por_consulta)} />
          <KpiCard title="Cirurgias por Consulta" value={pct(s.eficiencia.cirurgias_por_consulta)} />
          <KpiCard title="Ticket Médio Cirurgia" value={money.format(s.eficiencia.ticket_medio_cirurgia)} />
          <KpiCard title="Top Receita" value={rankingReceita ? rankingReceita.unidade : '-'} />
          <KpiCard title="Top Ticket" value={rankingTicket ? rankingTicket.unidade : '-'} />
          <KpiCard title="Top Conversão" value={rankingConv ? rankingConv.unidade : '-'} />
          <KpiCard title="Top Cirurgias" value={rankingCir ? rankingCir.unidade : '-'} />
        </div>
      </section>

      <section className="mt-6">
        <SectionTitle title="Financeiro e Fiscal" subtitle="Sem mistura com receita operacional" />
        <div className="grid gap-4 md:grid-cols-4">
          <KpiCard title="Receita Bruta" value={money.format(s.financeiro.receita_bruta)} />
          <KpiCard title="Receita Líquida" value={money.format(s.financeiro.receita_liquida)} />
          <KpiCard title="EBITDA" value={money.format(s.financeiro.ebitda)} />
          <KpiCard title="Margem EBITDA" value={pct(s.financeiro.margem_ebitda)} />
          <KpiCard title="Lucro Líquido" value={money.format(s.financeiro.lucro_liquido)} />
          <KpiCard title="Margem Líquida" value={pct(s.financeiro.margem_liquida)} />
          <KpiCard title="% Notas Fiscais" value={pct(s.fiscal.percentual_nf)} />
        </div>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="glass rounded-2xl p-4"><h3 className="mb-2 text-sm text-slate-300">Receita por unidade</h3><ResponsiveContainer width="100%" height={220}><BarChart data={payload.unidades}><CartesianGrid stroke="#334155" /><XAxis dataKey="unidade" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Bar dataKey="receita_operacional" fill="#14b8a6" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>
        <div className="glass rounded-2xl p-4"><h3 className="mb-2 text-sm text-slate-300">Ticket médio por unidade</h3><ResponsiveContainer width="100%" height={220}><BarChart data={payload.unidades}><CartesianGrid stroke="#334155" /><XAxis dataKey="unidade" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Bar dataKey="ticket_medio_cirurgia" fill="#6366f1" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>
        <div className="glass rounded-2xl p-4"><h3 className="mb-2 text-sm text-slate-300">Conversão consulta→cirurgia</h3><ResponsiveContainer width="100%" height={220}><BarChart data={payload.unidades}><CartesianGrid stroke="#334155" /><XAxis dataKey="unidade" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Bar dataKey="conv_consulta_cirurgia" fill="#f59e0b" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="glass rounded-2xl p-4"><h3 className="mb-2 text-sm text-slate-300">Funil</h3><ResponsiveContainer width="100%" height={220}><FunnelChart><Tooltip /><Funnel dataKey="value" data={funnelData} isAnimationActive /></FunnelChart></ResponsiveContainer></div>
        <div className="glass rounded-2xl p-4"><h3 className="mb-2 text-sm text-slate-300">EBITDA por mês</h3><ResponsiveContainer width="100%" height={220}><LineChart data={payload.financeiro.serie}><CartesianGrid stroke="#334155" /><XAxis dataKey="competencia" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Line dataKey="ebitda" stroke="#22d3ee" strokeWidth={2} /></LineChart></ResponsiveContainer></div>
        <div className="glass rounded-2xl p-4"><h3 className="mb-2 text-sm text-slate-300">Lucro líquido por mês</h3><ResponsiveContainer width="100%" height={220}><LineChart data={payload.financeiro.serie}><CartesianGrid stroke="#334155" /><XAxis dataKey="competencia" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Line dataKey="lucro_liquido" stroke="#a78bfa" strokeWidth={2} /></LineChart></ResponsiveContainer></div>
      </section>
    </div>
  );
}
