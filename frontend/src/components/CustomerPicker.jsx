import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, Plus, Search } from 'lucide-react';
import clsx from 'clsx';
import { customersApi } from '@/api/services';
import { useDebounce } from '@/hooks/useDebounce';
import CustomerFormModal from '@/pages/customers/CustomerFormModal';
import { useClickOutside } from '@/hooks/useClickOutside';

/** Server-side searchable customer select with "Add new customer" inline. onChange(customer object). */
export default function CustomerPicker({ value, onChange, invalid }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [adding, setAdding] = useState(null);
  const debounced = useDebounce(query, 250);
  const ref = useRef(null);
  const { data: results = [], isFetching } = useQuery({
    queryKey: ['customers', 'picker', debounced],
    queryFn: () => customersApi.list({ search: debounced, page_size: 15 }).then((d) => d.results),
    enabled: open,
  });
  const { data: selected } = useQuery({
    queryKey: ['customers', String(value)],
    queryFn: () => customersApi.get(value),
    enabled: !!value,
  });

  useClickOutside(ref, () => setOpen(false), open);

  const choose = (c) => {
    onChange(c);
    setOpen(false);
    setQuery('');
  };

  return (
    <div className="relative" ref={ref}>
      {open ? (
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            autoFocus
            className="input pl-8"
            placeholder="Search name or mobile…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setOpen(false);
              if (e.key === 'Enter' && results[0]) {
                e.preventDefault();
                choose(results[0]);
              }
            }}
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className={clsx(
            'input flex items-center justify-between text-left',
            invalid && 'border-red-500',
          )}
        >
          {selected && value ? (
            <span className="truncate">
              <b>{selected.name}</b>{' '}
              <span className="text-slate-500">
                · {selected.phone}
                {selected.city ? ` · ${selected.city}` : ''}
              </span>
            </span>
          ) : (
            <span className="text-slate-400">Select customer</span>
          )}
          <ChevronDown size={14} className="shrink-0 text-slate-400" />
        </button>
      )}
      {open && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-600 dark:bg-slate-800">
          <ul className="max-h-64 overflow-y-auto py-1">
            {!isFetching && results.length === 0 && (
              <li className="px-3 py-2 text-sm text-slate-500">No customer found</li>
            )}
            {results.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => choose(c)}
                  className="w-full px-3 py-2 text-left text-sm hover:bg-brand-50 dark:hover:bg-slate-700"
                >
                  <span className="font-medium">{c.name}</span>
                  <span className="block text-xs text-slate-500">
                    {c.phone}
                    {c.city ? ` · ${c.city}` : ''}
                    {c.state_code !== '33' ? ` · ${c.state_name}` : ''}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              setAdding({});
            }}
            className="flex w-full items-center gap-2 border-t border-slate-100 px-3 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50 dark:border-slate-700 dark:hover:bg-slate-700"
          >
            <Plus size={14} /> Add new customer{query ? ` "${query}"` : ''}
          </button>
        </div>
      )}
      <CustomerFormModal
        customer={adding}
        onClose={() => setAdding(null)}
        onSaved={(c) => choose(c)}
      />
    </div>
  );
}
