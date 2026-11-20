import { useEffect, useState } from 'react';
import { Search, X } from 'lucide-react';
import { useDebounce } from '@/hooks/useDebounce';

export default function SearchInput({
  value = '',
  onChange,
  placeholder = 'Search…',
  className = '',
}) {
  const [text, setText] = useState(value);
  const debounced = useDebounce(text);

  useEffect(() => {
    if (debounced !== value) onChange(debounced);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  return (
    <div className={`relative ${className}`}>
      <Search
        size={16}
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
      />
      <input
        className="input pl-9 pr-8"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        type="search"
      />
      {text && (
        <button
          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          onClick={() => setText('')}
          aria-label="Clear search"
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
}
