import clsx from 'clsx';
import { ArrowDown, ArrowUp, ArrowUpDown, Inbox } from 'lucide-react';
import Pagination from './Pagination';

/**
 * Generic list table used by every module.
 * columns: [{ key, header, render?: (row) => node, sortField?: 'api_field', className?, mobileHidden? }]
 * On phones each row becomes a card (first column is the title).
 */
export default function DataTable({
  columns,
  rows = [],
  loading,
  ordering,
  onSort,
  page,
  totalPages,
  count,
  pageSize,
  onPageChange,
  onRowClick,
  emptyText = 'No records found.',
  rowKey = 'id',
}) {
  const sortIcon = (field) => {
    if (!field) return null;
    if (ordering === field) return <ArrowUp size={14} />;
    if (ordering === `-${field}`) return <ArrowDown size={14} />;
    return <ArrowUpDown size={14} className="opacity-30" />;
  };
  const cell = (col, row) => (col.render ? col.render(row) : row[col.key]);

  return (
    <div className="card overflow-hidden p-0">
      {/* Desktop table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-900/40">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={clsx('whitespace-nowrap px-4 py-3 font-medium', col.className)}
                >
                  {col.sortField && onSort ? (
                    <button
                      className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-slate-800"
                      onClick={() => onSort(col.sortField)}
                    >
                      {col.header} {sortIcon(col.sortField)}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {loading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    {columns.map((col) => (
                      <td key={col.key} className="px-4 py-3">
                        <div className="h-4 w-3/4 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
                      </td>
                    ))}
                  </tr>
                ))
              : rows.map((row) => (
                  <tr
                    key={row[rowKey]}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={clsx(
                      onRowClick && 'cursor-pointer',
                      'hover:bg-slate-50 dark:hover:bg-slate-700/40',
                    )}
                  >
                    {columns.map((col) => (
                      <td key={col.key} className={clsx('px-4 py-3 align-middle', col.className)}>
                        {cell(col, row)}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="divide-y divide-slate-100 dark:divide-slate-700 md:hidden">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-2 p-4">
                <div className="h-4 w-1/2 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
                <div className="h-3 w-3/4 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
              </div>
            ))
          : rows.map((row) => (
              <div
                key={row[rowKey]}
                className="p-4"
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                <div className="mb-2 font-medium">{cell(columns[0], row)}</div>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
                  {columns
                    .slice(1)
                    .filter((c) => !c.mobileHidden)
                    .map((col) => (
                      <div key={col.key} className={col.key === 'actions' ? 'col-span-2 mt-1' : ''}>
                        {col.key !== 'actions' && (
                          <dt className="text-xs text-slate-500">{col.header}</dt>
                        )}
                        <dd>{cell(col, row)}</dd>
                      </div>
                    ))}
                </dl>
              </div>
            ))}
      </div>

      {!loading && rows.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-slate-500">
          <Inbox size={32} className="opacity-50" />
          <p className="text-sm">{emptyText}</p>
        </div>
      )}
      {onPageChange && (
        <Pagination
          page={page}
          totalPages={totalPages}
          count={count}
          pageSize={pageSize}
          onChange={onPageChange}
        />
      )}
    </div>
  );
}
