const config = {
  atualizado: {
    dot: 'bg-emerald-400',
    text: 'text-emerald-200',
    ring: 'ring-emerald-400/40',
    chip: 'bg-emerald-500/20 text-emerald-200',
    label: 'Atualizado',
  },
  atencao: {
    dot: 'bg-amber-400',
    text: 'text-amber-100',
    ring: 'ring-amber-400/40',
    chip: 'bg-amber-500/20 text-amber-200',
    label: 'Atenção',
  },
  desatualizado: {
    dot: 'bg-rose-400',
    text: 'text-rose-100',
    ring: 'ring-rose-400/40',
    chip: 'bg-rose-500/20 text-rose-200',
    label: 'Desatualizado',
  },
};

function getRelativeText(lastUpdate) {
  if (!lastUpdate) return 'Sem atualização registrada';
  const diffMs = Date.now() - new Date(lastUpdate).getTime();
  const minutes = Math.max(Math.floor(diffMs / 60000), 0);
  if (minutes < 60) return `Atualizado há ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `Atualizado há ${hours} h`;
}

export default function UpdateBadge({ status, lastUpdate }) {
  const item = config[status] || config.desatualizado;

  return (
    <div className={`highlight-card glass rounded-2xl p-5 ring-1 ${item.ring}`}>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Status da Base</p>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${item.chip}`}>{item.label}</span>
      </div>

      <div className={`flex items-center gap-2 text-lg font-semibold ${item.text}`}>
        <span className={`h-2.5 w-2.5 rounded-full ${item.dot} pulse-soft`} />
        {getRelativeText(lastUpdate)}
      </div>

      <p className="mt-3 text-xs text-slate-400">
        Última atualização: {lastUpdate ? new Date(lastUpdate).toLocaleString('pt-BR') : 'N/D'}
      </p>
    </div>
  );
}
