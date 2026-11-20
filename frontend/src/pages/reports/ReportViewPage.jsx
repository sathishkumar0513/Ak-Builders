import { useMemo, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import { FileSpreadsheet, FileText, X } from 'lucide-react';
import { categoriesApi, projectsApi, reportsApi, suppliersApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useListParams } from '@/hooks/useListParams';
import { useLookups } from '@/hooks/useLookups';
import BackLink from '@/components/ui/BackLink';
import PageHeader from '@/components/ui/PageHeader';
import Spinner from '@/components/ui/Spinner';
import { Input, Select } from '@/components/ui/Field';
import CustomerPicker from '@/components/CustomerPicker';
import { downloadBlob, openPdf } from '@/utils/documents';
import { EXPENSE_CATEGORIES } from '@/utils/constants';
import { formatDate, formatINR, formatQty, todayISO } from '@/utils/format';

const NUMERIC = new Set(['money', 'qty', 'number', 'percent']);
const PROJECT_STATUSES = [
  { value: 'PLANNED', label: 'Planned' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'ON_HOLD', label: 'On hold' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'CANCELLED', label: 'Cancelled' },
];
const GROUP_LABELS = {
  category: 'By category',
  project: 'By project',
  detail: 'Every entry',
  material: 'By material',
  supplier: 'By supplier',
  bill: 'Bill lines',
};

function fmt(v, type) {
  if (v === null || v === undefined || v === '') return '';
  if (type === 'money') return formatINR(v);
  if (type === 'qty') return formatQty(v);
  if (type === 'percent') return `${Number(v).toFixed(1)}%`;
  if (type === 'date') return formatDate(v);
  if (type === 'number') return Number(v).toLocaleString('en-IN');
  return String(v);
}

/** Local-time ISO date (toISOString would shift to UTC and lose a day in India). */
const iso = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

function presets() {
  const t = new Date();
  const fyStart = new Date(t.getMonth() >= 3 ? t.getFullYear() : t.getFullYear() - 1, 3, 1);
  return [
    { label: 'This month', from: iso(new Date(t.getFullYear(), t.getMonth(), 1)), to: todayISO() },
    {
      label: 'Last month',
      from: iso(new Date(t.getFullYear(), t.getMonth() - 1, 1)),
      to: iso(new Date(t.getFullYear(), t.getMonth(), 0)),
    },
    { label: 'This FY', from: iso(fyStart), to: todayISO() },
    {
      label: 'Last FY',
      from: iso(new Date(fyStart.getFullYear() - 1, 3, 1)),
      to: iso(new Date(fyStart.getFullYear(), 2, 31)),
    },
  ];
}

export default function ReportViewPage() {
  const { key } = useParams();
  const { params, setParams } = useListParams();
  const { payment_modes } = useLookups();
  const [busy, setBusy] = useState('');

  const { data: list = [] } = useQuery({
    queryKey: ['reports', 'list'],
    queryFn: reportsApi.list,
    staleTime: Infinity,
  });
  const meta = list.find((r) => r.key === key);
  const filters = meta?.filters || [];
  const has = (f) => filters.some((x) => x === f || x === `${f}!` || x.startsWith(`${f}:`));
  const groupSpec = filters.find((x) => x.startsWith('group:'));
  const groupOptions = groupSpec ? groupSpec.slice(6).split('|') : [];

  // only send what the user set; the server fills date defaults (financial year → today)
  const query = useMemo(() => {
    const q = { ...params };
    delete q.page;
    delete q.page_size;
    return q;
  }, [params]);
  const needsCustomer = filters.includes('customer!') && !query.customer;

  const {
    data: report,
    isLoading,
    isFetching,
    error,
  } = useQuery({
    queryKey: ['report', key, query],
    queryFn: () => reportsApi.run(key, query),
    enabled: !!meta && !needsCustomer,
    placeholderData: keepPreviousData,
    retry: 0,
  });

  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'for-expense'],
    queryFn: () => projectsApi.list({ page_size: 200 }).then((d) => d.results),
    enabled: has('project'),
    staleTime: 60_000,
  });
  const { data: suppliers = [] } = useQuery({
    queryKey: ['suppliers', 'all'],
    queryFn: () => suppliersApi.list({ page_size: 200 }).then((d) => d.results),
    enabled: has('supplier'),
    staleTime: 60_000,
  });
  const { data: categories = [] } = useQuery({
    queryKey: ['material-categories', 'all'],
    queryFn: () => categoriesApi.list({ page_size: 200 }).then((d) => d.results || d),
    enabled: has('material_category'),
    staleTime: 60_000,
  });

  const download = async (ext) => {
    setBusy(ext);
    try {
      if (ext === 'pdf') {
        const qs = new URLSearchParams({ ...query, export: 'pdf' }).toString();
        await openPdf(`/reports/${key}/?${qs}`);
      } else {
        const { blob, name } = await reportsApi.file(key, query, ext);
        downloadBlob(blob, name);
      }
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setBusy('');
    }
  };

  const dateFrom = query.date_from || report?.date_from || '';
  const dateTo = query.date_to || report?.date_to || '';
  const cols = report?.columns || [];

  return (
    <>
      <BackLink to="/reports">All reports</BackLink>
      <PageHeader
        title={meta?.title || 'Report'}
        subtitle={report?.subtitle || meta?.description || ' '}
        actions={
          <>
            <button
              className="btn-secondary"
              onClick={() => download('xlsx')}
              disabled={!report || !!busy || needsCustomer}
            >
              {busy === 'xlsx' ? <Spinner /> : <FileSpreadsheet size={16} />} Excel
            </button>
            <button
              className="btn-secondary"
              onClick={() => download('pdf')}
              disabled={!report || !!busy || needsCustomer}
            >
              {busy === 'pdf' ? <Spinner /> : <FileText size={16} />} PDF
            </button>
          </>
        }
      />

      {/* ---- filters ---- */}
      <div className="card mb-4 space-y-3">
        {has('dates') && (
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-sm">
              From
              <Input
                type="date"
                className="w-40"
                value={dateFrom}
                onChange={(e) => setParams({ date_from: e.target.value })}
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              To
              <Input
                type="date"
                className="w-40"
                value={dateTo}
                onChange={(e) => setParams({ date_to: e.target.value })}
              />
            </label>
            <div className="flex flex-wrap gap-1">
              {presets().map((p) => (
                <button
                  key={p.label}
                  className={clsx(
                    'rounded-full border px-3 py-1 text-xs',
                    dateFrom === p.from && dateTo === p.to
                      ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-900/30'
                      : 'border-slate-200 hover:border-slate-300 dark:border-slate-600',
                  )}
                  onClick={() => setParams({ date_from: p.from, date_to: p.to })}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {has('as_on') && (
            <label className="text-sm">
              <span className="mb-1 block text-slate-500">As on</span>
              <Input
                type="date"
                max={todayISO()}
                value={query.date_to || todayISO()}
                onChange={(e) => setParams({ date_to: e.target.value })}
              />
            </label>
          )}
          {has('customer') && (
            <div className="text-sm">
              <span className="mb-1 block text-slate-500">
                Customer{filters.includes('customer!') ? ' (required)' : ''}
              </span>
              <div className="flex gap-1">
                <div className="min-w-0 flex-1">
                  <CustomerPicker
                    value={query.customer || ''}
                    onChange={(c) => setParams({ customer: c.id })}
                    invalid={needsCustomer}
                  />
                </div>
                {query.customer && (
                  <button
                    className="btn-ghost px-2"
                    title="Clear"
                    onClick={() => setParams({ customer: '' })}
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            </div>
          )}
          {has('mode') && (
            <label className="text-sm">
              <span className="mb-1 block text-slate-500">Mode</span>
              <Select
                value={query.mode || ''}
                onChange={(e) => setParams({ mode: e.target.value })}
                placeholder="All modes"
                options={payment_modes}
              />
            </label>
          )}
          {has('project') && (
            <label className="text-sm">
              <span className="mb-1 block text-slate-500">Project</span>
              <Select
                value={query.project || ''}
                onChange={(e) => setParams({ project: e.target.value })}
                placeholder="All projects"
                options={projects.map((p) => ({ value: p.id, label: `${p.code} · ${p.name}` }))}
              />
            </label>
          )}
          {has('project_status') && (
            <label className="text-sm">
              <span className="mb-1 block text-slate-500">Status</span>
              <Select
                value={query.status || ''}
                onChange={(e) => setParams({ status: e.target.value })}
                placeholder="All except cancelled"
                options={PROJECT_STATUSES}
              />
            </label>
          )}
          {has('expense_category') && (
            <label className="text-sm">
              <span className="mb-1 block text-slate-500">Category</span>
              <Select
                value={query.category || ''}
                onChange={(e) => setParams({ category: e.target.value })}
                placeholder="All categories"
                options={EXPENSE_CATEGORIES}
              />
            </label>
          )}
          {has('material_category') && (
            <label className="text-sm">
              <span className="mb-1 block text-slate-500">Category</span>
              <Select
                value={query.category || ''}
                onChange={(e) => setParams({ category: e.target.value })}
                placeholder="All categories"
                options={categories.map((c) => ({ value: c.id, label: c.name }))}
              />
            </label>
          )}
          {has('supplier') && (
            <label className="text-sm">
              <span className="mb-1 block text-slate-500">Supplier</span>
              <Select
                value={query.supplier || ''}
                onChange={(e) => setParams({ supplier: e.target.value })}
                placeholder="All suppliers"
                options={suppliers.map((s) => ({ value: s.id, label: s.name }))}
              />
            </label>
          )}
          {(has('only_due') || has('low_only')) && (
            <label className="flex items-center gap-2 self-end pb-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 accent-brand-600"
                checked={query[has('only_due') ? 'only_due' : 'low_only'] === 'true'}
                onChange={(e) =>
                  setParams({
                    [has('only_due') ? 'only_due' : 'low_only']: e.target.checked ? 'true' : '',
                  })
                }
              />
              {has('only_due') ? 'Only customers with dues' : 'Only low-stock materials'}
            </label>
          )}
        </div>
        {groupOptions.length > 0 && (
          <div className="inline-flex rounded-lg border border-slate-200 p-0.5 dark:border-slate-600">
            {groupOptions.map((g, i) => {
              const active = (query.group || groupOptions[0]) === g;
              return (
                <button
                  key={g}
                  className={clsx(
                    'rounded-md px-3 py-1 text-sm',
                    active ? 'bg-brand-600 text-white' : 'text-slate-600 dark:text-slate-300',
                  )}
                  onClick={() => setParams({ group: i === 0 ? '' : g })}
                >
                  {GROUP_LABELS[g] || g}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {needsCustomer && (
        <div className="card text-center text-sm text-slate-500">
          Choose a customer to see their ledger.
        </div>
      )}
      {error && !needsCustomer && (
        <div className="card text-sm text-red-600">{getErrorMessage(error)}</div>
      )}

      {/* ---- KPI tiles ---- */}
      {report?.summary?.length > 0 && !needsCustomer && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {report.summary.map((k) => (
            <div key={k.label} className="card !p-3">
              <p className="truncate text-xs text-slate-500">{k.label}</p>
              <p className="mt-0.5 truncate text-lg font-semibold">{fmt(k.value, k.type)}</p>
            </div>
          ))}
        </div>
      )}

      {/* ---- table ---- */}
      {(isLoading || report) && !needsCustomer && (
        <div
          className={clsx(
            'card overflow-hidden !p-0 transition-opacity',
            isFetching && !isLoading && 'opacity-60',
          )}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800">
                <tr>
                  {cols.map((c) => (
                    <th
                      key={c.key}
                      className={clsx(
                        'whitespace-nowrap px-3 py-2.5 font-semibold',
                        NUMERIC.has(c.type) ? 'text-right' : 'text-left',
                      )}
                    >
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {isLoading &&
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      <td className="px-3 py-3" colSpan={cols.length || 1}>
                        <div className="h-4 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
                      </td>
                    </tr>
                  ))}
                {report?.rows.map((r, i) => (
                  <tr
                    key={i}
                    className={clsx(
                      'hover:bg-slate-50 dark:hover:bg-slate-800/50',
                      r._bold && 'font-semibold',
                    )}
                  >
                    {cols.map((c) => {
                      const v = r[c.key];
                      const neg = c.type === 'money' && Number(v) < 0;
                      return (
                        <td
                          key={c.key}
                          className={clsx(
                            'px-3 py-2',
                            NUMERIC.has(c.type) || c.type === 'date' || String(v ?? '').length <= 22
                              ? 'whitespace-nowrap'
                              : 'min-w-[12rem]',
                            NUMERIC.has(c.type) && 'text-right tabular-nums',
                            neg && 'text-red-600',
                            c.key === 'status' && v === 'Low' && 'font-medium text-red-600',
                          )}
                        >
                          {fmt(v, c.type)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {report && report.rows.length === 0 && (
                  <tr>
                    <td colSpan={cols.length} className="px-3 py-10 text-center text-slate-500">
                      No records for these filters.
                    </td>
                  </tr>
                )}
              </tbody>
              {report?.totals && report.rows.length > 0 && (
                <tfoot className="border-t-2 border-brand-500 bg-brand-50/60 font-semibold dark:bg-brand-900/20">
                  <tr>
                    {cols.map((c, i) => (
                      <td
                        key={c.key}
                        className={clsx(
                          'whitespace-nowrap px-3 py-2.5',
                          NUMERIC.has(c.type) && 'text-right tabular-nums',
                        )}
                      >
                        {i === 0
                          ? 'Total'
                          : c.key in report.totals
                            ? fmt(report.totals[c.key], c.type)
                            : ''}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
          {report && (
            <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500 dark:border-slate-700">
              {report.rows.length} row{report.rows.length === 1 ? '' : 's'}
            </p>
          )}
        </div>
      )}
    </>
  );
}
