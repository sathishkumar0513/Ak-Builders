import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import clsx from 'clsx';
import { Download, Plus } from 'lucide-react';
import { quotationsApi } from '@/api/services';
import { useListParams } from '@/hooks/useListParams';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Input } from '@/components/ui/Field';
import { exportCsv } from '@/utils/exportCsv';
import { formatDate, formatINR } from '@/utils/format';
import { QUOTATION_STATUS } from '@/utils/status';

const STATUSES = [
  ['', 'All'],
  ['DRAFT', 'Draft'],
  ['SENT', 'Sent'],
  ['APPROVED', 'Approved'],
  ['REJECTED', 'Rejected'],
  ['EXPIRED', 'Expired'],
  ['CONVERTED', 'Converted'],
];

export default function QuotationsPage() {
  const navigate = useNavigate();
  const { params, setParams, toggleOrdering } = useListParams({ ordering: '-quotation_date' });
  const { data, isLoading } = useQuery({
    queryKey: ['quotations', params],
    queryFn: () => quotationsApi.list(params),
    placeholderData: keepPreviousData,
  });

  const onExport = async () => {
    const all = await quotationsApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-quotations',
      [
        { header: 'Number', value: (q) => q.number },
        { header: 'Rev', value: (q) => q.revision },
        { header: 'Date', value: (q) => formatDate(q.quotation_date) },
        { header: 'Valid until', value: (q) => formatDate(q.valid_until) },
        { header: 'Customer', value: (q) => q.customer_name },
        { header: 'Mobile', value: (q) => q.customer_phone },
        { header: 'Title', value: (q) => q.title },
        { header: 'Status', value: (q) => q.status_display },
        { header: 'Amount', value: (q) => q.grand_total },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'number',
      header: 'Quotation',
      sortField: 'number',
      render: (q) => (
        <div>
          <p className="font-medium">
            {q.number} <span className="text-xs font-normal text-slate-500">Rev {q.revision}</span>
          </p>
          <p className="text-xs text-slate-500">{q.customer_name}</p>
        </div>
      ),
    },
    {
      key: 'title',
      header: 'Work',
      mobileHidden: true,
      render: (q) => <span className="line-clamp-1">{q.title || '—'}</span>,
    },
    {
      key: 'date',
      header: 'Date',
      sortField: 'quotation_date',
      render: (q) => formatDate(q.quotation_date),
    },
    {
      key: 'valid',
      header: 'Valid until',
      sortField: 'valid_until',
      render: (q) => (
        <span
          className={
            q.status === 'SENT' && q.valid_until < new Date().toISOString().slice(0, 10)
              ? 'text-red-600'
              : ''
          }
        >
          {formatDate(q.valid_until)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (q) => <Badge color={QUOTATION_STATUS[q.status]}>{q.status_display}</Badge>,
    },
    {
      key: 'amount',
      header: 'Amount',
      sortField: 'grand_total',
      className: 'text-right',
      render: (q) => <span className="font-medium">{formatINR(q.grand_total)}</span>,
    },
  ];

  return (
    <>
      <PageHeader
        title="Quotations"
        subtitle={data ? `${data.count} quotations (latest revisions)` : ' '}
        actions={
          <>
            <button className="btn-secondary" onClick={onExport}>
              <Download size={16} /> Export CSV
            </button>
            <Link to="/quotations/new" className="btn-primary">
              <Plus size={16} /> New quotation
            </Link>
          </>
        }
      />
      <div className="no-scrollbar mb-3 flex gap-1 overflow-x-auto">
        {STATUSES.map(([v, l]) => (
          <button
            key={v}
            onClick={() => setParams({ status: v })}
            className={clsx(
              'whitespace-nowrap rounded-full px-3 py-1 text-sm',
              (params.status || '') === v
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
          placeholder="Number, customer, mobile, work, item"
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
        onRowClick={(q) => navigate(`/quotations/${q.id}`)}
        emptyText="No quotations yet. Click 'New quotation' to create one."
      />
    </>
  );
}
