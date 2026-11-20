import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import clsx from 'clsx';
import { AlertTriangle, Download, Plus } from 'lucide-react';
import { invoicesApi } from '@/api/services';
import { useListParams } from '@/hooks/useListParams';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Input } from '@/components/ui/Field';
import { exportCsv } from '@/utils/exportCsv';
import { formatDate, formatINR } from '@/utils/format';
import { INVOICE_STATUS } from '@/utils/status';

const CHIPS = [
  ['', 'All'],
  ['UNPAID', 'Unpaid'],
  ['PARTIAL', 'Part paid'],
  ['PAID', 'Paid'],
  ['overdue', 'Overdue'],
  ['CANCELLED', 'Cancelled'],
];

export default function InvoicesPage() {
  const navigate = useNavigate();
  const { params, setParams, toggleOrdering } = useListParams({ ordering: '-invoice_date' });
  const { data, isLoading } = useQuery({
    queryKey: ['invoices', params],
    queryFn: () => invoicesApi.list(params),
    placeholderData: keepPreviousData,
  });
  const { data: overdue } = useQuery({
    queryKey: ['invoices', 'overdue-summary'],
    queryFn: () => invoicesApi.collection('overdue'),
  });
  const chip = params.overdue === 'true' ? 'overdue' : params.status || '';
  const setChip = (v) =>
    setParams(v === 'overdue' ? { overdue: 'true', status: '' } : { status: v, overdue: '' });

  const onExport = async () => {
    const all = await invoicesApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-invoices',
      [
        { header: 'Invoice', value: (i) => i.number },
        { header: 'Date', value: (i) => formatDate(i.invoice_date) },
        { header: 'Due', value: (i) => formatDate(i.due_date) },
        { header: 'Customer', value: (i) => i.customer_name },
        { header: 'Project', value: (i) => i.project_code },
        { header: 'Status', value: (i) => i.status_display },
        { header: 'Total', value: (i) => i.grand_total },
        { header: 'Advance adjusted', value: (i) => i.advance_adjusted },
        { header: 'Paid', value: (i) => i.amount_paid },
        { header: 'Balance', value: (i) => i.balance_due },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'n',
      header: 'Invoice',
      sortField: 'number',
      render: (i) => (
        <div>
          <p className="font-medium">{i.number}</p>
          <p className="text-xs text-slate-500">
            {i.customer_name}
            {i.project_code ? ` · ${i.project_code}` : ''}
          </p>
        </div>
      ),
    },
    {
      key: 'd',
      header: 'Date',
      sortField: 'invoice_date',
      render: (i) => formatDate(i.invoice_date),
    },
    {
      key: 'due',
      header: 'Due',
      sortField: 'due_date',
      render: (i) => (
        <span className={i.is_overdue ? 'font-medium text-red-600' : ''}>
          {formatDate(i.due_date)}
        </span>
      ),
    },
    {
      key: 's',
      header: 'Status',
      render: (i) => (
        <span className="flex gap-1">
          <Badge color={INVOICE_STATUS[i.status]}>{i.status_display}</Badge>
          {i.is_overdue && <Badge color="red">Overdue</Badge>}
        </span>
      ),
    },
    {
      key: 't',
      header: 'Total',
      sortField: 'grand_total',
      className: 'text-right',
      render: (i) => formatINR(i.grand_total),
    },
    {
      key: 'b',
      header: 'Balance',
      sortField: 'balance_due',
      className: 'text-right',
      render: (i) =>
        Number(i.balance_due) > 0 ? (
          <span className="font-medium text-red-600">{formatINR(i.balance_due)}</span>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Invoices"
        subtitle="GST tax invoices"
        actions={
          <>
            <button className="btn-secondary" onClick={onExport}>
              <Download size={16} /> Export CSV
            </button>
            <Link to="/invoices/new" className="btn-primary">
              <Plus size={16} /> New invoice
            </Link>
          </>
        }
      />
      {overdue?.count > 0 && chip !== 'overdue' && (
        <button
          onClick={() => setChip('overdue')}
          className="mb-3 flex w-full items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-left text-sm text-red-800 hover:bg-red-100 dark:border-red-800 dark:bg-red-900/30 dark:text-red-200"
        >
          <AlertTriangle size={16} /> <b>{overdue.count}</b> overdue invoice
          {overdue.count > 1 ? 's' : ''} · <b>{formatINR(overdue.total)}</b> pending — click to view
          and send reminders
        </button>
      )}
      <div className="no-scrollbar mb-3 flex gap-1 overflow-x-auto">
        {CHIPS.map(([v, l]) => (
          <button
            key={v}
            onClick={() => setChip(v)}
            className={clsx(
              'whitespace-nowrap rounded-full px-3 py-1 text-sm',
              chip === v
                ? 'bg-brand-600 text-white'
                : 'bg-white text-slate-600 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300',
            )}
          >
            {l}
          </button>
        ))}
      </div>
      <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_150px_150px]">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Invoice no., customer, mobile, project, item"
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
        onRowClick={(i) => navigate(`/invoices/${i.id}`)}
        emptyText="No invoices match."
      />
    </>
  );
}
