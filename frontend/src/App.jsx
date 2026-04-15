import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Funnel, FunnelChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import KpiCard from './components/KpiCard';
import UpdateBadge from './components/UpdateBadge';
import FinancialDreCard from './components/FinancialDreCard';
import ReportButton from './components/ReportButton';
import StatusUnidadesPanel from './components/StatusUnidadesPanel';
import { getDashboardBundle, getFilterOptions } from './lib/api';

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const integer = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const pct = (v) => `${((v || 0) * 100).toFixed(1)}%`;
const safeNumber = (value) => (typeof value === 'number' && Number.isFinite(value) ? value : null);

const SectionTitle = ({ title, subtitle }) => (
  <div className="mb-3 flex items-end justify-between gap-2">
    <div>
      <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
      {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
    </div>
  </div>
);

const EmptyState = () => (
  <div className="glass rounded-2xl p-6 text-sm text-slate-300">Nenhum dado encontrado para os filtros selecionados.</div>
);

const ChartOrEmpty = ({ title, hasData, children }) => (
  <div className="glass rounded-2xl p-4">
    <h3 className="mb-2 text-sm text-slate-300">{title}</h3>
    {hasData ? children : <p className="py-16 text-center text-sm text-slate-400">Nenhum dado encontrado para os filtros selecionados.</p>}
  </div>
);

const TableCell = ({ children, className = '' }) => <td className={`whitespace-nowrap px-3 py-2 text-sm text-slate-200 ${className}`}>{children}</td>;

const AlertChip = ({ label, value, color }) => (
  <div className={`rounded-lg border px-3 py-2 text-xs ${color}`}>
    <p className="uppercase tracking-wide">{label}</p>
    <p className="mt-1 text-lg font-semibold">{value}</p>
  </div>
);

export default function App() {
  const [payload, setPayload] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({ anos: [], meses: [], competencias: [], unidades: [], profissionais: [] });
  const [expandedAlertGroups, setExpandedAlertGroups] = useState({});
  const [filterOptions, setFilterOptions] = useState({ anos: [], meses: [], competencias: [], unidades: [], profissionais: [] });

  const fetchData = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await getDashboardBundle(filters);
      setPayload(data);
    } catch {
      setError('Não foi possível carregar o dashboard agora. Verifique a conexão e tente novamente.');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchOptions = async () => {
    try {
      const opts = await getFilterOptions();
      setFilterOptions(opts);
    } catch {
      // silently ignore - options will be populated from payload as fallback
    }
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 60_000);
    return () => clearInterval(id);
  }, [JSON.stringify(filters)]);

  useEffect(() => {
    fetchOptions();
    const id = setInterval(fetchOptions, 300_000);
    return () => clearInterval(id);
  }, []);

  const options = useMemo(() => {
    // Fonte primária: endpoint dedicado de opções
    if (filterOptions.anos.length > 0 || filterOptions.unidades.length > 0) {
      return filterOptions;
    }
    // Fallback: derivar do payload enquanto as opções não carregam
    const anos = new Set();
    const meses = new Set();
    const competencias = new Set();

    const addComp = (comp) => {
      if (!comp) return;
      competencias.add(comp);
      const [a, m] = String(comp).split('-');
      if (a && Number(a) > 0) anos.add(Number(a));
      if (m && Number(m) > 0) meses.add(Number(m));
    };

    (payload?.financeiro?.serie || []).forEach((x) => addComp(x.competencia));
    (payload?.fiscal?.serie || []).forEach((x) => addComp(x.competencia));

    return {
      anos: [...anos].filter(Boolean).sort((a, b) => a - b),
      meses: [...meses].filter(Boolean).sort((a, b) => a - b),
      competencias: [...competencias].sort(),
      unidades: [...new Set((payload?.unidades || []).map((u) => u.unidade))].filter(Boolean).sort(),
      profissionais: [...new Set((payload?.profissionais || []).map((p) => p.profissional))].filter(Boolean).sort(),
    };
  }, [payload, filterOptions]);

  const groupedAlerts = useMemo(() => {
    const groups = {};
    (payload?.alertas || []).forEach((alerta) => {
      const key = alerta.categoria || 'geral';
      if (!groups[key]) groups[key] = [];
      groups[key].push(alerta);
    });
    return groups;
  }, [payload]);

  const profissionaisTable = useMemo(() => {
    const unidades = payload?.unidades || [];
    const profissionais = payload?.profissionais || [];
    const totalReceita = unidades.reduce((acc, u) => acc + (safeNumber(u.receita_operacional) || 0), 0);

    const unidadeMap = unidades.reduce((acc, u) => {
      acc[u.unidade] = {
        receita: safeNumber(u.receita_operacional) || 0,
        cirurgias: safeNumber(u.cirurgias) || 0,
      };
      return acc;
    }, {});

    const professionalsPerUnit = profissionais.reduce((acc, p) => {
      if (!p.unidade) return acc;
      if (!acc[p.unidade]) acc[p.unidade] = new Set();
      acc[p.unidade].add(p.profissional);
      return acc;
    }, {});

    return profissionais
      .map((p) => {
        const unidade = unidadeMap[p.unidade] || { receita: 0, cirurgias: 0 };
        const cirurgiasProf = safeNumber(p.cirurgias) || 0;
        const consultas = safeNumber(p.consultas_totais);

        // Receita estimada proporcional às cirurgias dentro da unidade.
        const receitaEstimada = unidade.cirurgias > 0 ? (cirurgiasProf / unidade.cirurgias) * unidade.receita : null;
        const participacao = receitaEstimada !== null && totalReceita > 0 ? receitaEstimada / totalReceita : null;

        return {
          profissional: p.profissional || '—',
          unidade: p.unidade || '—',
          receita: receitaEstimada,
          ticketMedio: receitaEstimada !== null && cirurgiasProf > 0 ? receitaEstimada / cirurgiasProf : null,
          atendimentos: consultas,
          cirurgias: cirurgiasProf || null,
          conversao: consultas && consultas > 0 ? cirurgiasProf / consultas : null,
          participacao,
          profissionaisNaUnidade: professionalsPerUnit[p.unidade]?.size || null,
        };
      })
      .sort((a, b) => (safeNumber(b.receita) || -1) - (safeNumber(a.receita) || -1));
  }, [payload]);

  const unidadesTable = useMemo(() => {
    const profissionaisPorUnidade = (payload?.profissionais || []).reduce((acc, p) => {
      if (!p.unidade) return acc;
      if (!acc[p.unidade]) acc[p.unidade] = new Set();
      acc[p.unidade].add(p.profissional);
      return acc;
    }, {});

    return [...(payload?.unidades || [])]
      .map((u) => {
        const receita = safeNumber(u.receita_operacional);
        const quantidadeProfissionais = profissionaisPorUnidade[u.unidade]?.size || 0;
        return {
          unidade: u.unidade || '—',
          receita,
          ticketMedio: safeNumber(u.ticket_medio_cirurgia),
          atendimentos: safeNumber(u.consultas_totais),
          cirurgias: safeNumber(u.cirurgias),
          conversao: safeNumber(u.conv_consulta_cirurgia),
          receitaPorProfissional: receita !== null && quantidadeProfissionais > 0 ? receita / quantidadeProfissionais : null,
          mesIncompleto: Boolean(u.mes_incompleto),
          dadosInconsistentes: Boolean(u.dados_inconsistentes),
        };
      })
      .sort((a, b) => (safeNumber(b.receita) || -1) - (safeNumber(a.receita) || -1));
  }, [payload]);

  if (isLoading && !payload) return <div className="min-h-screen bg-slateDeep p-6 text-slate-100">Carregando dashboard premium...</div>;

  if (error && !payload) {
    return (
      <div className="min-h-screen bg-slateDeep p-6 text-slate-100">
        <div className="glass mx-auto mt-10 max-w-xl rounded-2xl p-6">
          <h2 className="text-lg font-semibold">Falha ao carregar dashboard</h2>
          <p className="mt-2 text-sm text-slate-300">{error}</p>
          <button
            type="button"
            onClick={fetchData}
            className="mt-4 rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
          >
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  const s = payload?.summary;
  const unidades = payload?.unidades || [];
  const financeiroSerie = payload?.financeiro?.serie || [];
  const funnelData = [
    { value: s?.funil?.leads || 0, name: 'Leads' },
    { value: s?.funil?.consultas || 0, name: 'Consultas' },
    { value: s?.funil?.cirurgias || 0, name: 'Cirurgias' },
  ];

  const rankingReceita = [...unidades].sort((a, b) => (safeNumber(b.receita_operacional) || 0) - (safeNumber(a.receita_operacional) || 0))[0];
  const rankingTicket = [...unidades].sort((a, b) => (safeNumber(b.ticket_medio_cirurgia) || 0) - (safeNumber(a.ticket_medio_cirurgia) || 0))[0];
  const rankingConv = [...unidades].sort((a, b) => (safeNumber(b.conv_consulta_cirurgia) || 0) - (safeNumber(a.conv_consulta_cirurgia) || 0))[0];
  const rankingCir = [...unidades].sort((a, b) => (safeNumber(b.cirurgias) || 0) - (safeNumber(a.cirurgias) || 0))[0];

  return (
    <div className="min-h-screen bg-slateDeep px-4 py-6 text-slate-100 md:px-6 md:py-8">
      <header className="mb-6 grid gap-4 lg:grid-cols-[1fr_360px] lg:items-start">
        <div className="glass rounded-2xl p-6">
          <h1 className="text-3xl font-semibold">ICB Executive Dashboard</h1>
          <p className="mt-2 text-sm text-slate-400">Visão premium com separação operacional, financeira e fiscal.</p>
          <div className="mt-4 grid gap-3 md:grid-cols-3 xl:grid-cols-5">
            {['anos', 'meses', 'competencias', 'unidades', 'profissionais'].map((k) => (
              <select
                key={k}
                className="rounded-xl border border-slate-700/70 bg-slate-900/70 p-3 text-sm outline-none transition focus:border-cyan-400"
                onChange={(e) => setFilters((f) => ({ ...f, [k]: e.target.value ? [e.target.value] : [] }))}
                value={filters[k]?.[0] || ''}
              >
                <option value="">{k === 'competencias' ? 'Todas competências' : `Todos ${k}`}</option>
                {options[k].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            ))}
          </div>
        </div>

        <div className="flex flex-col items-end gap-3">
          <UpdateBadge status={payload?.lastUpdate?.status} lastUpdate={payload?.lastUpdate?.last_update} />
          <ReportButton />
        </div>
      </header>

      {error && (
        <section className="mb-6">
          <div className="glass rounded-2xl border border-rose-500/30 p-4">
            <p className="text-sm text-rose-200">{error}</p>
            <button
              type="button"
              onClick={fetchData}
              className="mt-3 rounded-lg bg-rose-400/20 px-3 py-2 text-sm font-semibold text-rose-100 transition hover:bg-rose-400/30"
            >
              Tentar novamente
            </button>
          </div>
        </section>
      )}

      <StatusUnidadesPanel data={payload?.unidadesStatus} />

      <section>
        <SectionTitle title="ALERTAS EXECUTIVOS" subtitle="Monitoramento por severidade e categoria" />
        {(payload?.alertas || []).length > 0 ? (
          <div className="glass rounded-2xl p-4">
            <div className="mb-4 grid gap-2 sm:grid-cols-3">
              <AlertChip label="Críticos" value={(payload.alertas || []).filter((a) => a.nivel === 'critico').length} color="border-rose-400/40 bg-rose-400/10 text-rose-100" />
              <AlertChip label="Atenção" value={(payload.alertas || []).filter((a) => a.nivel === 'atencao').length} color="border-amber-400/40 bg-amber-400/10 text-amber-100" />
              <AlertChip label="Info" value={(payload.alertas || []).filter((a) => a.nivel === 'info').length} color="border-cyan-400/40 bg-cyan-400/10 text-cyan-100" />
            </div>

            <div className="space-y-3">
              {Object.entries(groupedAlerts).map(([categoria, items]) => {
                const expanded = Boolean(expandedAlertGroups[categoria]);
                return (
                  <div key={categoria} className="rounded-xl border border-slate-700/60 bg-slate-900/40">
                    <button
                      type="button"
                      onClick={() => setExpandedAlertGroups((prev) => ({ ...prev, [categoria]: !expanded }))}
                      className="flex w-full items-center justify-between px-4 py-3 text-left"
                    >
                      <span className="text-sm font-semibold uppercase tracking-wide text-slate-200">{categoria}</span>
                      <span className="text-xs text-slate-400">{items.length} alerta(s) {expanded ? '▲' : '▼'}</span>
                    </button>
                    {expanded && (
                      <div className="space-y-2 border-t border-slate-700/60 px-4 py-3">
                        {items.map((alerta, idx) => (
                          <div key={`${categoria}-${idx}`} className="rounded-lg border border-slate-700/50 bg-slate-950/40 p-3">
                            <p className="text-sm font-semibold text-slate-100">{alerta.titulo || 'Alerta'}</p>
                            <p className="mt-1 text-xs text-slate-300">{alerta.detalhe || 'Sem detalhe disponível.'}</p>
                            {Array.isArray(alerta.unidades) && alerta.unidades.length > 0 && (
                              <p className="mt-2 text-xs text-slate-400">Unidades: {alerta.unidades.join(', ')}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <EmptyState />
        )}
      </section>

      <section className="mt-6">
        <SectionTitle title="Funil Operacional" subtitle="Leads → Consultas → Cirurgias e conversões" />
        <div className="grid gap-4 md:grid-cols-5">
          <KpiCard title="Leads" value={integer.format(s?.funil?.leads || 0)} tooltip="Total de leads." />
          <KpiCard title="Consultas" value={integer.format(s?.funil?.consultas || 0)} tooltip="Consultas totais = presenciais + online." />
          <KpiCard title="Cirurgias" value={integer.format(s?.funil?.cirurgias || 0)} tooltip="Total de cirurgias." />
          <KpiCard title="Conv. Lead → Consulta" value={pct(s?.funil?.conv_lead_consulta)} tooltip="consultas_totais / leads" />
          <KpiCard title="Conv. Consulta → Cirurgia" value={pct(s?.funil?.conv_consulta_cirurgia)} tooltip="cirurgias / consultas_totais" />
        </div>
      </section>

      <section className="mt-6">
        <SectionTitle title="Eficiência e Ranking" subtitle="Indicadores de produtividade e comparação entre unidades" />
        <div className="grid gap-4 md:grid-cols-4">
          <KpiCard title="Receita por Lead" value={money.format(s?.eficiencia?.receita_por_lead || 0)} />
          <KpiCard title="Receita por Consulta" value={money.format(s?.eficiencia?.receita_por_consulta || 0)} />
          <KpiCard title="Cirurgias por Consulta" value={pct(s?.eficiencia?.cirurgias_por_consulta)} />
          <KpiCard title="Ticket Médio Cirurgia" value={money.format(s?.eficiencia?.ticket_medio_cirurgia || 0)} />
          <KpiCard title="Top Receita" value={rankingReceita ? rankingReceita.unidade : '-'} />
          <KpiCard title="Top Ticket" value={rankingTicket ? rankingTicket.unidade : '-'} />
          <KpiCard title="Top Conversão" value={rankingConv ? rankingConv.unidade : '-'} />
          <KpiCard title="Top Cirurgias" value={rankingCir ? rankingCir.unidade : '-'} />
        </div>
      </section>

      <section className="mt-6">
        <SectionTitle title="Financeiro e Fiscal" subtitle="Sem mistura com receita operacional" />
        <div className="grid gap-4 md:grid-cols-4">
          <KpiCard title="Receita Bruta" value={money.format(s?.financeiro?.receita_bruta || 0)} />
          <KpiCard title="Receita Líquida" value={money.format(s?.financeiro?.receita_liquida || 0)} />
          <KpiCard title="EBITDA" value={money.format(s?.financeiro?.ebitda || 0)} />
          <KpiCard title="Margem EBITDA" value={pct(s?.financeiro?.margem_ebitda)} />
          <KpiCard title="Lucro Líquido" value={money.format(s?.financeiro?.lucro_liquido || 0)} />
          <KpiCard title="Margem Líquida" value={pct(s?.financeiro?.margem_liquida)} />
          <KpiCard title="% Notas Fiscais" value={pct(s?.fiscal?.percentual_nf)} />
        </div>
      </section>

      <FinancialDreCard
        summaryFinanceiro={s?.financeiro}
        financeiroSerie={financeiroSerie}
        unidades={unidades}
      />

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <ChartOrEmpty title="Receita por unidade" hasData={unidades.length > 0}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={unidades}><CartesianGrid stroke="#334155" /><XAxis dataKey="unidade" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Bar dataKey="receita_operacional" fill="#14b8a6" radius={[6, 6, 0, 0]} /></BarChart>
          </ResponsiveContainer>
        </ChartOrEmpty>
        <ChartOrEmpty title="Ticket médio por unidade" hasData={unidades.length > 0}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={unidades}><CartesianGrid stroke="#334155" /><XAxis dataKey="unidade" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Bar dataKey="ticket_medio_cirurgia" fill="#6366f1" radius={[6, 6, 0, 0]} /></BarChart>
          </ResponsiveContainer>
        </ChartOrEmpty>
        <ChartOrEmpty title="Conversão consulta→cirurgia" hasData={unidades.length > 0}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={unidades}><CartesianGrid stroke="#334155" /><XAxis dataKey="unidade" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Bar dataKey="conv_consulta_cirurgia" fill="#f59e0b" radius={[6, 6, 0, 0]} /></BarChart>
          </ResponsiveContainer>
        </ChartOrEmpty>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <ChartOrEmpty title="Funil" hasData={funnelData.some((d) => d.value > 0)}>
          <ResponsiveContainer width="100%" height={220}><FunnelChart><Tooltip /><Funnel dataKey="value" data={funnelData} isAnimationActive /></FunnelChart></ResponsiveContainer>
        </ChartOrEmpty>
        <ChartOrEmpty title="EBITDA por mês" hasData={financeiroSerie.length > 0}>
          <ResponsiveContainer width="100%" height={220}><LineChart data={financeiroSerie}><CartesianGrid stroke="#334155" /><XAxis dataKey="competencia" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Line dataKey="ebitda" stroke="#22d3ee" strokeWidth={2} /></LineChart></ResponsiveContainer>
        </ChartOrEmpty>
        <ChartOrEmpty title="Lucro líquido por mês" hasData={financeiroSerie.length > 0}>
          <ResponsiveContainer width="100%" height={220}><LineChart data={financeiroSerie}><CartesianGrid stroke="#334155" /><XAxis dataKey="competencia" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Line dataKey="lucro_liquido" stroke="#a78bfa" strokeWidth={2} /></LineChart></ResponsiveContainer>
        </ChartOrEmpty>
      </section>

      <section className="mt-6">
        <SectionTitle title="Profissionais" subtitle="Performance individual (ordenado por receita)" />
        {profissionaisTable.length > 0 ? (
          <div className="glass overflow-x-auto rounded-2xl p-4">
            <table className="min-w-full text-left">
              <thead>
                <tr className="border-b border-slate-700 text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-3 py-2">Profissional</th>
                  <th className="px-3 py-2">Unidade</th>
                  <th className="px-3 py-2">Receita</th>
                  <th className="px-3 py-2">Ticket médio</th>
                  <th className="px-3 py-2">Nº atendimentos</th>
                  <th className="px-3 py-2">Nº cirurgias</th>
                  <th className="px-3 py-2">Conversão</th>
                  <th className="px-3 py-2">Participação na receita</th>
                </tr>
              </thead>
              <tbody>
                {profissionaisTable.map((row, idx) => (
                  <tr key={`${row.profissional}-${row.unidade}-${idx}`} className="border-b border-slate-800/70 last:border-b-0">
                    <TableCell>{row.profissional}</TableCell>
                    <TableCell>{row.unidade}</TableCell>
                    <TableCell>{safeNumber(row.receita) !== null ? money.format(row.receita) : '—'}</TableCell>
                    <TableCell>{safeNumber(row.ticketMedio) !== null ? money.format(row.ticketMedio) : '—'}</TableCell>
                    <TableCell>{safeNumber(row.atendimentos) !== null ? integer.format(row.atendimentos) : '—'}</TableCell>
                    <TableCell>{safeNumber(row.cirurgias) !== null ? integer.format(row.cirurgias) : '—'}</TableCell>
                    <TableCell>{safeNumber(row.conversao) !== null ? pct(row.conversao) : '—'}</TableCell>
                    <TableCell>{safeNumber(row.participacao) !== null ? pct(row.participacao) : '—'}</TableCell>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState />
        )}
      </section>

      <section className="mt-6">
        <SectionTitle title="Unidades" subtitle="Visão gerencial por unidade" />
        {unidadesTable.length > 0 ? (
          <div className="glass overflow-x-auto rounded-2xl p-4">
            <table className="min-w-full text-left">
              <thead>
                <tr className="border-b border-slate-700 text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-3 py-2">Unidade</th>
                  <th className="px-3 py-2">Receita total</th>
                  <th className="px-3 py-2">Ticket médio</th>
                  <th className="px-3 py-2">Nº atendimentos</th>
                  <th className="px-3 py-2">Nº cirurgias</th>
                  <th className="px-3 py-2">Conversão</th>
                  <th className="px-3 py-2">Receita por profissional</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {unidadesTable.map((row) => {
                  const statusText = row.dadosInconsistentes ? 'Inconsistente' : row.mesIncompleto ? 'Mês incompleto' : 'Completo';
                  const statusColor = row.dadosInconsistentes ? 'text-rose-300' : row.mesIncompleto ? 'text-amber-300' : 'text-emerald-300';
                  return (
                    <tr key={row.unidade} className="border-b border-slate-800/70 last:border-b-0">
                      <TableCell>{row.unidade}</TableCell>
                      <TableCell>{safeNumber(row.receita) !== null ? money.format(row.receita) : '—'}</TableCell>
                      <TableCell>{safeNumber(row.ticketMedio) !== null ? money.format(row.ticketMedio) : '—'}</TableCell>
                      <TableCell>{safeNumber(row.atendimentos) !== null ? integer.format(row.atendimentos) : '—'}</TableCell>
                      <TableCell>{safeNumber(row.cirurgias) !== null ? integer.format(row.cirurgias) : '—'}</TableCell>
                      <TableCell>{safeNumber(row.conversao) !== null ? pct(row.conversao) : '—'}</TableCell>
                      <TableCell>{safeNumber(row.receitaPorProfissional) !== null ? money.format(row.receitaPorProfissional) : '—'}</TableCell>
                      <TableCell><span className={statusColor}>{statusText}</span></TableCell>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState />
        )}
      </section>
    </div>
  );
}
