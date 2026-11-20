export default function StatCard({ label, value, icon: Icon, hint }) {
  return (
    <div className="card flex items-start justify-between">
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="mt-1 text-2xl font-semibold">{value}</p>
        {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
      </div>
      {Icon && (
        <div className="rounded-lg bg-brand-50 p-2 text-brand-600 dark:bg-brand-900/30">
          <Icon size={20} />
        </div>
      )}
    </div>
  );
}
