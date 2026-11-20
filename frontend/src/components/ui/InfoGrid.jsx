/** Label/value pairs in a responsive grid: items = [[label, value], ...] */
export default function InfoGrid({ items, cols = 'sm:grid-cols-2 lg:grid-cols-4' }) {
  return (
    <dl className={`grid grid-cols-2 gap-x-4 gap-y-3 text-sm ${cols}`}>
      {items.filter(Boolean).map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-xs text-slate-500">{label}</dt>
          <dd className="break-words font-medium">
            {value === '' || value === null || value === undefined ? '—' : value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
