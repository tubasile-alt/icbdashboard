import { useEffect, useMemo, useState } from 'react';

import { getExecutiveReport } from '../lib/api';

const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const pct = (value) => (typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : 'n/d');

const statusConfig = {
  atualizado: {
    label: 'Dados confiáveis',
    chip: 'bg-emerald-500/15 text-emerald-200 border-emerald-400/40',
  },
  atencao: {
    label: 'Atenção',
    chip: 'bg-amber-500/15 text-amber-100 border-amber-400/40',
  },
  desatualizado: {
    label: 'Desatualizado',
    chip: 'bg-rose-500/15 text-rose-100 border-rose-400/40',
  },
};

const card = 'rounded-2xl border border-slate-700/70 bg-slate-900/50 shadow-[0_20px_50px_rgba(2,8,23,0.35)]';

function ValueWithDelta({ value, qoq, yoy }) {
  return (
    <div>
      <p className="text-3xl font-semibold text-slate-100">{typeof value === 'number' ? money.format(value) : 'n/d'}</p>
      <div className="mt-2 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full border border-slate-600/80 bg-slate-800/70 px-2 py-1 text-slate-300">QoQ: {pct(qoq)}</span>
        <span className="rounded-full border border-slate-600/80 bg-slate-800/70 px-2 py-1 text-slate-300">YoY: {pct(yoy)}</span>
      </div>
    </div>
  );
}

function AlertLevel({ nivel }) {
  if (nivel === 'critico') return <span className="rounded-full border border-rose-500/50 bg-rose-500/15 px-2 py-0.5 text-xs text-rose-200">Crítico</span>;
  if (nivel === 'atencao') return <span className="rounded-full border border-amber-500/50 bg-amber-500/15 px-2 py-0.5 text-xs text-amber-200">Atenção</span>;
  if (nivel === 'positivo') return <span className="rounded-full border border-emerald-500/50 bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-200">Positivo</span>;
  return <span className="rounded-full border border-cyan-500/50 bg-cyan-500/15 px-2 py-0.5 text-xs text-cyan-200">Info</span>;
}

export default function ExecutiveReportPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const payload = await getExecutiveReport();
        if (active) setData(payload);
      } catch {
        if (active) setError('Falha ao carregar relatório executivo.');
      } finally {
        if (active) setLoading(false);
      }
    };

    load();
    const id = setInterval(load, 60_000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const status = statusConfig[data?.header?.status] || statusConfig.desatualizado;

  const saude = data?.resumo_executivo?.saude_rede || {};
  const indicadores = data?.indicadores_operacionais || {};
  const totalAlertas = useMemo(() => (data?.alertas?.items || []).length, [data]);

  if (loading && !data) {
    return <div className="min-h-screen bg-slateDeep p-8 text-slate-100">Carregando relatório executivo…</div>;
  }

  if (error && !data) {
    return <div className="min-h-screen bg-slateDeep p-8 text-rose-200">{error}</div>;
  }

  return (
    <div className="min-h-screen bg-slateDeep px-4 py-6 text-slate-100 md:px-7 md:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className={`${card} p-6`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">ICB · Executive Finance Control</p>
              <h1 className="mt-2 text-3xl font-semibold">{data?.header?.title || 'Painel Executivo'}</h1>
              <p className="mt-1 text-sm text-slate-400">{data?.header?.subtitle || 'Uso interno · Confidencial'}</p>
            </div>

            <div className="text-right">
              <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${status.chip}`}>{status.label}</span>
              <p className="mt-2 text-xs text-slate-400">
                Última atualização: {data?.header?.last_update ? new Date(data.header.last_update).toLocaleString('pt-BR') : 'n/d'}
              </p>
            </div>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <article className={`${card} p-5`}>
            <p className="text-xs uppercase tracking-wide text-slate-400">Receita Bruta</p>
            <ValueWithDelta
              value={data?.resumo_executivo?.receita_bruta}
              qoq={data?.resumo_executivo?.variacao_qoq?.receita_bruta}
              yoy={data?.resumo_executivo?.variacao_yoy?.receita_bruta}
            />
          </article>
          <article className={`${card} p-5`}>
            <p className="text-xs uppercase tracking-wide text-slate-400">EBITDA</p>
            <ValueWithDelta
              value={data?.resumo_executivo?.ebitda}
              qoq={data?.resumo_executivo?.variacao_qoq?.ebitda}
              yoy={data?.resumo_executivo?.variacao_yoy?.ebitda}
            />
          </article>
          <article className={`${card} p-5`}>
            <p className="text-xs uppercase tracking-wide text-slate-400">Lucro Líquido</p>
            <ValueWithDelta
              value={data?.resumo_executivo?.lucro_liquido}
              qoq={data?.resumo_executivo?.variacao_qoq?.lucro_liquido}
              yoy={data?.resumo_executivo?.variacao_yoy?.lucro_liquido}
            />
          </article>
          <article className={`${card} p-5`}>
            <p className="text-xs uppercase tracking-wide text-slate-400">Saúde da Rede</p>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <p className="rounded-lg bg-slate-800/80 p-2">Saudáveis: <b>{saude.saudaveis || 0}</b></p>
              <p className="rounded-lg bg-slate-800/80 p-2">Atenção: <b>{saude.atencao || 0}</b></p>
              <p className="rounded-lg bg-slate-800/80 p-2">Risco: <b>{saude.risco || 0}</b></p>
              <p className="rounded-lg bg-slate-800/80 p-2">Encerradas: <b>{saude.encerradas || 0}</b></p>
            </div>
          </article>
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
          <article className={`${card} p-5`}>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Alertas e Ações</h2>
              <span className="text-xs text-slate-400">{totalAlertas} alerta(s)</span>
            </div>
            <div className="space-y-2">
              {(data?.alertas?.items || []).slice(0, 8).map((alerta, idx) => (
                <div key={`${alerta.alert_id}-${idx}`} className="rounded-xl border border-slate-700/70 bg-slate-950/50 p-3">
                  <div className="mb-1 flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-100">{alerta.titulo}</p>
                    <AlertLevel nivel={alerta.nivel} />
                  </div>
                  <p className="text-xs text-slate-300">{alerta.detalhe}</p>
                  {Array.isArray(alerta.unidades) && alerta.unidades.length > 0 && (
                    <p className="mt-1 text-xs text-slate-400">Unidades afetadas: {alerta.unidades.join(', ')}</p>
                  )}
                </div>
              ))}
            </div>
          </article>

          <article className={`${card} p-5`}>
            <h2 className="text-lg font-semibold">Unidades a avaliar para fechamento</h2>
            <div className="mt-3 space-y-2">
              {(data?.alertas?.avaliacao_fechamento || []).map((item) => (
                <div key={item.unidade} className="rounded-xl border border-slate-700/70 bg-slate-950/50 p-3 text-sm">
                  <p className="font-semibold text-slate-100">{item.unidade}</p>
                  <p className="text-xs text-slate-300">{item.motivo}</p>
                  <p className="mt-1 text-xs text-slate-400">Status: {item.status} · EBITDA: {typeof item.ebitda === 'number' ? money.format(item.ebitda) : 'n/d'}</p>
                </div>
              ))}
              {(data?.alertas?.avaliacao_fechamento || []).length === 0 && <p className="text-sm text-slate-400">Nenhuma unidade sinalizada.</p>}
            </div>
          </article>
        </section>

        <section className={`${card} p-5`}>
          <h2 className="text-lg font-semibold">DRE Consolidada</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-left">
              <thead>
                <tr className="border-b border-slate-700 text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-2 py-2">Linha</th>
                  <th className="px-2 py-2">Valor atual</th>
                  <th className="px-2 py-2">QoQ</th>
                  <th className="px-2 py-2">YoY</th>
                </tr>
              </thead>
              <tbody>
                {(data?.dre_consolidada?.linhas || []).map((row) => (
                  <tr key={row.linha} className="border-b border-slate-800/80 text-sm">
                    <td className="px-2 py-2 text-slate-200">{row.linha}</td>
                    <td className="px-2 py-2">{typeof row.valor_atual === 'number' ? money.format(row.valor_atual) : 'n/d'}</td>
                    <td className="px-2 py-2">{row.tem_qoq ? pct(row.variacao_qoq) : 'n/d'}</td>
                    <td className="px-2 py-2">{row.tem_yoy ? pct(row.variacao_yoy) : 'n/d'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-2">
          <article className={`${card} p-5`}>
            <h2 className="text-lg font-semibold">TOP 5 EBITDA</h2>
            <div className="mt-3 space-y-2">
              {(data?.ranking?.top_5 || []).map((item, i) => (
                <div key={`${item.unidade}-top`} className="flex items-center justify-between rounded-lg bg-slate-950/40 px-3 py-2 text-sm">
                  <p>{i + 1}. {item.unidade}</p>
                  <p className="font-semibold">{money.format(item.valor)} <span className="text-xs text-slate-400">({item.metrica})</span></p>
                </div>
              ))}
            </div>
          </article>

          <article className={`${card} p-5`}>
            <h2 className="text-lg font-semibold">BOTTOM 5 EBITDA</h2>
            <div className="mt-3 space-y-2">
              {(data?.ranking?.bottom_5 || []).map((item, i) => (
                <div key={`${item.unidade}-bottom`} className="flex items-center justify-between rounded-lg bg-slate-950/40 px-3 py-2 text-sm">
                  <p>{i + 1}. {item.unidade}</p>
                  <p className="font-semibold">{money.format(item.valor)} <span className="text-xs text-slate-400">({item.metrica})</span></p>
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="grid gap-4 xl:grid-cols-2">
          <article className={`${card} p-5`}>
            <h2 className="text-lg font-semibold">Pipeline Financeiro</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <p className="rounded-xl bg-slate-950/50 p-3 text-sm">Leads Ativos<br /><span className="text-xl font-semibold">{Math.round(data?.pipeline_financeiro?.leads_ativos || 0)}</span></p>
              <p className="rounded-xl bg-slate-950/50 p-3 text-sm">Cirurgias esperadas<br /><span className="text-xl font-semibold">{Math.round(data?.pipeline_financeiro?.cirurgias_esperadas || 0)}</span></p>
              <p className="rounded-xl bg-slate-950/50 p-3 text-sm">Potencial Receita<br /><span className="text-xl font-semibold">{money.format(data?.pipeline_financeiro?.potencial_receita || 0)}</span></p>
            </div>
            <p className="mt-2 text-xs text-slate-400">{data?.pipeline_financeiro?.metodo}</p>
          </article>

          <article className={`${card} p-5`}>
            <h2 className="text-lg font-semibold">Indicadores Operacionais</h2>
            <div className="mt-3 space-y-2 text-sm text-slate-200">
              <p>Conversão: <b>{pct(indicadores.conversao_media_rede)}</b> · {indicadores?.unidade_critica_conversao?.unidade || 'n/d'}: {pct(indicadores?.unidade_critica_conversao?.valor)}</p>
              <p>Ticket Médio: <b>{money.format(indicadores.ticket_medio_rede || 0)}</b> · {indicadores?.unidade_ticket_abaixo?.unidade || 'n/d'}: {money.format(indicadores?.unidade_ticket_abaixo?.valor || 0)}</p>
            </div>
          </article>
        </section>

        <footer className={`${card} p-5`}>
          <h2 className="text-lg font-semibold">Qualidade de Dados</h2>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-300">
            {(data?.qualidade_dados?.flags || []).map((flag) => <li key={flag}>{flag}</li>)}
            {(data?.qualidade_dados?.flags || []).length === 0 && <li>Sem alertas de qualidade no recorte atual.</li>}
          </ul>
        </footer>
      </div>
    </div>
  );
}
