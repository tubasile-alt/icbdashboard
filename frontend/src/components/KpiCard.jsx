export default function KpiCard({ title, value, tooltip }) {
  return (
    <div className="glass rounded-2xl p-4 transition duration-300 hover:-translate-y-0.5 hover:border-slate-500/50">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400" title={tooltip || ''}>
        {title}
      </p>
      <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
      {tooltip && <p className="mt-2 text-xs text-slate-500">{tooltip}</p>}
    </div>
  );
}
