import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Download, Plus } from 'lucide-react';
import { advancesApi } from '@/api/services';
import { useListParams } from '@/hooks/useListParams';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Input, Select } from '@/components/ui/Field';
import { exportCsv } from '@/utils/exportCsv';
import { formatDate, formatINR } from '@/utils/format';
import { ADVANCE_STATUS } from '@/utils/status';
import AdvanceModal from './AdvanceModal';

export default function AdvancesPage() {
  const navigate = useNavigate();
  const { params, setParams, toggleOrdering } = useListParams({ ordering: '-date' });
  const [adding, setAdding] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ['advances', params],
    queryFn: () => advancesApi.list(params),
    placeholderData: keepPreviousData,
  });
  const unused = (data?.results || []).reduce((s, a) => s + Number(a.balance), 0);

  const onExport = async () => {
    const all = await advancesApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-advances',
      [
        { header: 'Receipt', value: (a) => a.receipt_number },
        { header: 'Date', value: (a) => formatDate(a.date) },
        { header: 'Customer', value: (a) => a.customer_name },
        { header: 'Project', value: (a) => a.project_code },
        { header: 'Mode', value: (a) => a.mode_display },
        { header: 'Amount', value: (a) => a.amount },
        { header: 'Adjusted', value: (a) => a.adjusted_amount },
        { header: 'Refunded', value: (a) => a.refunded_amount },
        { header: 'Balance', value: (a) => a.balance },
        { header: 'Status', value: (a) => a.status_display },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'r',
      header: 'Receipt',
      sortField: 'receipt_number',
      render: (a) => (
        <div>
          <p className="font-medium">{a.receipt_number}</p>
          <p className="text-xs text-slate-500">{a.customer_name}</p>
        </div>
      ),
    },
    { key: 'date', header: 'Date', sortField: 'date', render: (a) => formatDate(a.date) },
    { key: 'proj', header: 'Project', mobileHidden: true, render: (a) => a.project_code || '—' },
    { key: 'mode', header: 'Mode', render: (a) => a.mode_display },
    {
      key: 'amt',
      header: 'Amount',
      sortField: 'amount',
      className: 'text-right',
      render: (a) => formatINR(a.amount),
    },
    {
      key: 'bal',
      header: 'Unused',
      className: 'text-right',
      render: (a) =>
        Number(a.balance) > 0 ? (
          <span className="font-medium text-green-700">{formatINR(a.balance)}</span>
        ) : (
          '—'
        ),
    },
    {
      key: 'st',
      header: 'Status',
      render: (a) => <Badge color={ADVANCE_STATUS[a.status]}>{a.status_display}</Badge>,
    },
  ];

  return (
    <>
      <PageHeader
        title="Advances"
        subtitle={data ? `${data.count} advances · ${formatINR(unused)} unused on this page` : ' '}
        actions={
          <>
            <button className="btn-secondary" onClick={onExport}>
              <Download size={16} /> Export CSV
            </button>
            <button className="btn-primary" onClick={() => setAdding(true)}>
              <Plus size={16} /> Record advance
            </button>
          </>
        }
      />
      <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-[1fr_180px_150px_150px]">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Receipt, customer, mobile, UTR, project"
        />
        <Select
          value={params.status || ''}
          onChange={(e) => setParams({ status: e.target.value })}
          placeholder="All statuses"
          options={[
            { value: 'OPEN', label: 'Unused' },
            { value: 'PARTIAL', label: 'Partly adjusted' },
            { value: 'ADJUSTED', label: 'Fully adjusted' },
            { value: 'REFUNDED', label: 'Refunded' },
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
        onRowClick={(a) => navigate(`/advances/${a.id}`)}
        emptyText="No advances yet."
      />
      <AdvanceModal
        open={adding}
        onClose={() => setAdding(false)}
        onSaved={(a) => navigate(`/advances/${a.id}`)}
      />
    </>
  );
}
