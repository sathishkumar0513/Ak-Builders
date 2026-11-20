import { useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { CheckCircle2, Download, Paperclip, Pencil, Plus, Trash2 } from 'lucide-react';
import { expensesApi, projectsApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { useListParams } from '@/hooks/useListParams';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Input, Select } from '@/components/ui/Field';
import { EXPENSE_CATEGORIES } from '@/utils/constants';
import { exportCsv } from '@/utils/exportCsv';
import { formatDate, formatINR } from '@/utils/format';
import ExpenseModal from './ExpenseModal';

/** Expense list with live totals by category. Also used inside the project page (projectId). */
export function ExpenseList({ projectId, compact = false }) {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { hasRole, user } = useAuth();
  const finance = hasRole('ADMIN', 'ACCOUNTANT');
  const admin = hasRole('ADMIN');
  const { params, setParams, toggleOrdering } = useListParams({ ordering: '-date' });
  const query = { ...params, ...(projectId ? { project: projectId } : {}) };
  const [editing, setEditing] = useState(null); // null | 'new' | expense

  const { data, isLoading } = useQuery({
    queryKey: ['expenses', query],
    queryFn: () => expensesApi.list(query),
    placeholderData: keepPreviousData,
  });
  const { data: summary } = useQuery({
    queryKey: ['expenses', 'summary', { ...query, page: undefined, ordering: undefined }],
    queryFn: () => expensesApi.collection('summary', { ...query, page: undefined }),
    placeholderData: keepPreviousData,
  });
  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'for-expense'],
    queryFn: () =>
      projectsApi
        .list({ page_size: 200 })
        .then((d) => d.results.filter((p) => p.status !== 'CANCELLED')),
    enabled: !projectId,
    staleTime: 60_000,
  });

  const refresh = () =>
    ['expenses', 'projects', 'dashboard'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));

  const approve = async (e) => {
    try {
      await expensesApi.action(e.id, 'approve');
      toast.success(`${e.voucher_number} approved`);
      refresh();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };
  const remove = async (e) => {
    if (
      !(await confirm({
        title: `Delete ${e.voucher_number}?`,
        message: `${formatINR(e.amount)} will be removed from ${e.project_code || 'office expenses'}. It stays in the audit log.`,
        confirmText: 'Delete',
        danger: true,
      }))
    )
      return;
    try {
      await expensesApi.remove(e.id);
      toast.success('Expense deleted');
      refresh();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };
  const canEdit = (e) => finance || (!e.is_approved && e.created_by === user?.id);

  const onExport = async () => {
    const all = await expensesApi.list({ ...query, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-expenses',
      [
        { header: 'Voucher', value: (e) => e.voucher_number },
        { header: 'Date', value: (e) => formatDate(e.date) },
        { header: 'Category', value: (e) => e.category_display },
        { header: 'Project', value: (e) => e.project_code || 'Office' },
        { header: 'Paid to', value: (e) => e.paid_to },
        { header: 'Description', value: (e) => e.description },
        { header: 'Workers', value: (e) => e.workers_count ?? '' },
        { header: 'Days', value: (e) => e.work_days ?? '' },
        { header: 'Mode', value: (e) => e.mode_display },
        { header: 'Reference', value: (e) => e.reference_number },
        { header: 'Approved', value: (e) => (e.is_approved ? 'Yes' : 'Pending') },
        { header: 'Entered by', value: (e) => e.created_by_name },
        { header: 'Amount', value: (e) => e.amount },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'v',
      header: 'Voucher',
      sortField: 'date',
      render: (e) => (
        <div>
          <p className="font-medium">{e.voucher_number}</p>
          <p className="text-xs text-slate-500">{formatDate(e.date)}</p>
        </div>
      ),
    },
    {
      key: 'c',
      header: 'Category',
      sortField: 'category',
      render: (e) => (
        <div>
          <p>{e.category_display}</p>
          {e.workers_count ? (
            <p className="text-xs text-slate-500">
              {e.workers_count} workers × {Number(e.work_days || 1)} day
              {Number(e.work_days) === 1 ? '' : 's'}
            </p>
          ) : null}
        </div>
      ),
    },
    ...(projectId
      ? []
      : [
          {
            key: 'p',
            header: 'Project',
            render: (e) =>
              e.project ? (
                <Link
                  to={`/projects/${e.project}`}
                  className="text-brand-700 hover:underline"
                  onClick={(ev) => ev.stopPropagation()}
                >
                  {e.project_code}
                </Link>
              ) : (
                <span className="text-slate-500">Office</span>
              ),
          },
        ]),
    {
      key: 'd',
      header: 'Paid to / details',
      render: (e) => (
        <div className="max-w-xs">
          <p className="truncate">{e.paid_to || '—'}</p>
          <p className="truncate text-xs text-slate-500">
            {[e.mode_display, e.reference_number, e.description].filter(Boolean).join(' · ')}
          </p>
        </div>
      ),
    },
    {
      key: 's',
      header: 'Status',
      render: (e) =>
        e.is_approved ? (
          <Badge color="green">Approved</Badge>
        ) : (
          <Badge color="amber">Pending</Badge>
        ),
    },
    {
      key: 'a',
      header: 'Amount',
      sortField: 'amount',
      className: 'text-right',
      render: (e) => <span className="font-medium">{formatINR(e.amount)}</span>,
    },
    {
      key: 'x',
      header: '',
      className: 'text-right',
      render: (e) => (
        <div className="flex justify-end" onClick={(ev) => ev.stopPropagation()}>
          {e.bill_attachment && (
            <a
              href={e.bill_attachment}
              target="_blank"
              rel="noreferrer"
              className="btn-ghost px-2"
              title="View bill"
            >
              <Paperclip size={16} />
            </a>
          )}
          {finance && !e.is_approved && (
            <button
              className="btn-ghost px-2 text-green-700"
              title="Approve"
              onClick={() => approve(e)}
            >
              <CheckCircle2 size={16} />
            </button>
          )}
          {canEdit(e) && (
            <button className="btn-ghost px-2" title="Edit" onClick={() => setEditing(e)}>
              <Pencil size={16} />
            </button>
          )}
          {admin && (
            <button
              className="btn-ghost px-2 text-red-600"
              title="Delete"
              onClick={() => remove(e)}
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      ),
    },
  ];

  const byCat = summary?.by_category || [];

  return (
    <>
      {!compact && (
        <PageHeader
          title="Expenses"
          subtitle={
            summary
              ? `${summary.count} entries · ${formatINR(summary.total)}${
                  summary.pending_approval
                    ? ` · ${summary.pending_approval} waiting for approval`
                    : ''
                }`
              : ' '
          }
          actions={
            <>
              <button className="btn-secondary" onClick={onExport}>
                <Download size={16} /> Export CSV
              </button>
              <button className="btn-primary" onClick={() => setEditing('new')}>
                <Plus size={16} /> Add expense
              </button>
            </>
          }
        />
      )}
      {compact && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-slate-500">
            {summary ? `${summary.count} entries · ` : ''}
            <b className="text-slate-800 dark:text-slate-100">{formatINR(summary?.total)}</b>
            {summary?.pending_approval ? ` · ${summary.pending_approval} pending approval` : ''}
          </p>
          <button className="btn-primary" onClick={() => setEditing('new')}>
            <Plus size={16} /> Add expense
          </button>
        </div>
      )}

      {byCat.length > 0 && (
        <div className="no-scrollbar mb-3 flex gap-2 overflow-x-auto pb-1">
          {byCat.map((c) => {
            const active = params.category === c.category;
            return (
              <button
                key={c.category}
                onClick={() => setParams({ category: active ? '' : c.category })}
                className={`shrink-0 rounded-lg border px-3 py-1.5 text-left text-xs transition ${
                  active
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/30'
                    : 'border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800'
                }`}
              >
                <span className="block text-slate-500">{c.label}</span>
                <b className="text-sm">{formatINR(c.total)}</b>
              </button>
            );
          })}
        </div>
      )}

      <div
        className={`mb-3 grid gap-2 sm:grid-cols-2 ${
          projectId
            ? 'lg:grid-cols-[1fr_170px_150px_150px_150px]'
            : 'lg:grid-cols-[1fr_170px_200px_150px_150px_150px]'
        }`}
      >
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Voucher, paid to, description"
        />
        <Select
          value={params.category || ''}
          onChange={(e) => setParams({ category: e.target.value })}
          placeholder="All categories"
          options={EXPENSE_CATEGORIES}
        />
        {!projectId && (
          <Select
            value={params.project || (params.overhead === 'true' ? 'office' : '')}
            onChange={(e) =>
              e.target.value === 'office'
                ? setParams({ project: '', overhead: 'true' })
                : setParams({ project: e.target.value, overhead: '' })
            }
            placeholder="All projects"
            options={[
              ...(finance ? [{ value: 'office', label: 'Office / overhead only' }] : []),
              ...projects.map((p) => ({ value: p.id, label: `${p.code} · ${p.name}` })),
            ]}
          />
        )}
        <Select
          value={params.approved || ''}
          onChange={(e) => setParams({ approved: e.target.value })}
          placeholder="Any status"
          options={[
            { value: 'false', label: 'Waiting for approval' },
            { value: 'true', label: 'Approved' },
          ]}
        />
        <Input
          type="date"
          value={params.date_from || ''}
          onChange={(e) => setParams({ date_from: e.target.value })}
          title="From"
        />
        <Input
          type="date"
          value={params.date_to || ''}
          onChange={(e) => setParams({ date_to: e.target.value })}
          title="To"
        />
      </div>
      <DataTable
        columns={columns}
        rows={data?.results}
        loading={isLoading}
        ordering={params.ordering}
        onSort={toggleOrdering}
        page={params.page}
        totalPages={data?.total_pages}
        count={data?.count}
        pageSize={params.page_size}
        onPageChange={(p) => setParams({ page: p }, { resetPage: false })}
        emptyText="No expenses recorded."
      />
      <ExpenseModal
        open={!!editing}
        onClose={() => setEditing(null)}
        expense={editing === 'new' ? null : editing}
        projectId={projectId}
      />
    </>
  );
}

export default function ExpensesPage() {
  return <ExpenseList />;
}
