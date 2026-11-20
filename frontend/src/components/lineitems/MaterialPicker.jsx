import { useMemo, useRef, useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import clsx from 'clsx';
import { useMaterialCatalog } from '@/hooks/useMaterialCatalog';
import { formatINR, formatQty } from '@/utils/format';
import { useClickOutside } from '@/hooks/useClickOutside';

/**
 * Searchable material dropdown. onSelect(material) gives the full material object so the
 * caller can auto-fill rate, unit, HSN and GST. priceField: 'purchase_price' | 'selling_price'.
 */
export default function MaterialPicker({
  value,
  onSelect,
  priceField = 'selling_price',
  invalid,
  placeholder = 'Select material',
}) {
  const { data: materials = [] } = useMaterialCatalog();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState(0);
  const ref = useRef(null);

  const selected = materials.find((m) => m.id === Number(value));
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? materials.filter((m) =>
          `${m.name} ${m.brand} ${m.category_name} ${m.hsn_code}`.toLowerCase().includes(q),
        )
      : materials;
    return list.slice(0, 50);
  }, [materials, query]);

  useClickOutside(ref, () => setOpen(false), open);

  const choose = (m) => {
    onSelect(m);
    setOpen(false);
    setQuery('');
  };

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === 'Enter' && open && filtered[highlight]) {
      e.preventDefault();
      choose(filtered[highlight]);
    } else if (e.key === 'Escape') setOpen(false);
  };

  return (
    <div className="relative" ref={ref}>
      {open ? (
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            autoFocus
            className="input pl-8"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setHighlight(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Type name, brand or HSN…"
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className={clsx(
            'input flex items-center justify-between text-left',
            invalid && 'border-red-500',
            !selected && 'text-slate-400',
          )}
        >
          <span className="truncate">
            {selected ? `${selected.name} ${selected.brand}`.trim() : placeholder}
          </span>
          <ChevronDown size={14} className="shrink-0 text-slate-400" />
        </button>
      )}
      {open && (
        <ul className="absolute z-30 mt-1 max-h-72 w-full min-w-[280px] overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-600 dark:bg-slate-800">
          {filtered.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500">No matching material</li>
          )}
          {filtered.map((m, i) => (
            <li key={m.id}>
              <button
                type="button"
                onMouseEnter={() => setHighlight(i)}
                onClick={() => choose(m)}
                className={clsx(
                  'flex w-full items-start justify-between gap-2 px-3 py-2 text-left text-sm',
                  i === highlight && 'bg-brand-50 dark:bg-slate-700',
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">
                    {m.name} {m.brand}
                  </span>
                  <span className="block text-xs text-slate-500">
                    {m.category_name} · Stock {formatQty(m.stock_quantity)} {m.unit}
                    {m.is_low_stock && <span className="ml-1 text-red-600">(low)</span>}
                  </span>
                </span>
                {m[priceField] !== undefined && (
                  <span className="shrink-0 text-xs text-slate-600 dark:text-slate-300">
                    {formatINR(m[priceField])}/{m.unit}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
