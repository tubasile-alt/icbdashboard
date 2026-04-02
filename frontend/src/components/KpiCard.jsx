export default function KpiCard({ title, value }) {
  return (
    <div className="glass rounded-xl p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}
