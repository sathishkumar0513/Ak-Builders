import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function Pagination({ page, totalPages, count, pageSize, onChange }) {
  if (!count) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);
  return (
    <div className="flex items-center justify-between gap-2 border-t border-slate-200 px-4 py-3 text-sm dark:border-slate-700">
      <p className="text-slate-500">
        {from}–{to} of {count}
      </p>
      <div className="flex items-center gap-1">
        <button
          className="btn-secondary px-2 py-1"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          aria-label="Previous page"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="px-2">
          {page} / {totalPages}
        </span>
        <button
          className="btn-secondary px-2 py-1"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
          aria-label="Next page"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
