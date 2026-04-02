const config = {
  updated: {
    dot: 'bg-emerald-400',
    text: 'text-emerald-300',
    label: '🟢 Atualizado recentemente',
  },
  attention: {
    dot: 'bg-amber-400',
    text: 'text-amber-300',
    label: '🟡 Atenção na atualização',
  },
  stale: {
    dot: 'bg-rose-400',
    text: 'text-rose-300',
    label: '🔴 Dados desatualizados',
  },
};

function getRelativeText(lastUpdate) {
  if (!lastUpdate) return 'sem atualização';
  const diffMs = Date.now() - new Date(lastUpdate).getTime();
  const minutes = Math.max(Math.floor(diffMs / 60000), 0);
  if (minutes < 60) return `Atualizado há ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `Atualizado há ${hours}h`;
}

export default function UpdateBadge({ status, lastUpdate }) {
  const minutesSince = lastUpdate ? (Date.now() - new Date(lastUpdate).getTime()) / 60000 : 9999;
  const effectiveStatus = status === 'updated' && minutesSince > 60 ? 'attention' : status;
  const item = config[effectiveStatus] || config.stale;

  return (
    <div className="glass rounded-xl p-4">
      <div className={`flex items-center gap-2 font-semibold ${item.text}`}>
        <span className={`h-2.5 w-2.5 rounded-full ${item.dot} pulse-soft`} />
        <span>{item.label}</span>
      </div>
      <div className="mt-2 text-sm text-slate-200">{getRelativeText(lastUpdate)}</div>
      <div className="text-xs text-slate-400">
        Última atualização:{' '}
        {lastUpdate ? new Date(lastUpdate).toLocaleString('pt-BR') : 'N/D'}
      </div>
    </div>
  );
}
