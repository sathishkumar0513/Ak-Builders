import clsx from 'clsx';

export default function Tabs({ tabs, active, onChange }) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-700">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={clsx(
            '-mb-px whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium',
            active === t.id
              ? 'border-brand-600 text-brand-600'
              : 'border-transparent text-slate-500 hover:text-slate-700',
          )}
        >
          {t.label}
          {t.count !== undefined && (
            <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 text-xs dark:bg-slate-700">
              {t.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
