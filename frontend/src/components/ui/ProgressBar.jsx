export default function ProgressBar({ value, wide }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={`h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700 ${wide ? 'w-full' : 'w-20'}`}
      >
        <div
          className="h-full bg-brand-500"
          style={{ width: `${Math.min(100, Number(value || 0))}%` }}
        />
      </div>
      <span className="text-xs text-slate-500">{Number(value || 0).toFixed(0)}%</span>
    </div>
  );
}
