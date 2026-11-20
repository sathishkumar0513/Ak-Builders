import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Download, Plus } from 'lucide-react';
import { purchasesApi, suppliersApi } from '@/api/services';
import { useListParams } from '@/hooks/useListParams';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Input, Select } from '@/components/ui/Field';
import { exportCsv } from '@/utils/exportCsv';
import { formatDate, formatINR } from '@/utils/format';
import { PAYMENT_STATUS, PURCHASE_STATUS } from '@/utils/status';

export default function PurchasesPage() {
  const navigate = useNavigate();
  const { params, setParams, toggleOrdering } = useListParams({ ordering: '-purchase_date' });
  const { data, isLoading } = useQuery({
    queryKey: ['purchases', params],
    queryFn: () => purchasesApi.list(params),
    placeholderData: keepPreviousData,
  });
  const { data: suppliers = [] } = useQuery({
    queryKey: ['suppliers', 'all'],
    queryFn: () => suppliersApi.list({ page_size: 200 }).then((d) => d.results),
  });

  const onExport = async () => {
    const all = await purchasesApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-purchases',
      [
        { header: 'PO number', value: (p) => p.po_number },
        { header: 'Date', value: (p) => formatDate(p.purchase_date) },
        { header: 'Supplier', value: (p) => p.supplier_name },
        { header: 'Bill no.', value: (p) => p.supplier_invoice_number },
        { header: 'Status', value: (p) => p.status_display },
        { header: 'Payment', value: (p) => p.payment_status_display },
        { header: 'Total', value: (p) => p.grand_total },
        { header: 'Paid', value: (p) => p.amount_paid },
        { header: 'Due', value: (p) => p.balance_due },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'po',
      header: 'PO number',
      sortField: 'po_number',
      render: (p) => (
        <div>
          <p className="font-medium">{p.po_number}</p>
          <p className="text-xs text-slate-500">{p.supplier_name}</p>
        </div>
      ),
    },
    {
      key: 'date',
      header: 'Date',
      sortField: 'purchase_date',
      render: (p) => formatDate(p.purchase_date),
    },
    {
      key: 'bill',
      header: 'Bill no.',
      mobileHidden: true,
      render: (p) => p.supplier_invoice_number || '—',
    },
    {
      key: 'status',
      header: 'Goods',
      render: (p) => <Badge color={PURCHASE_STATUS[p.status]}>{p.status_display}</Badge>,
    },
    {
      key: 'pay',
      header: 'Payment',
      render: (p) =>
        p.status !== 'CANCELLED' && (
          <Badge color={PAYMENT_STATUS[p.payment_status]}>{p.payment_status_display}</Badge>
        ),
    },
    {
      key: 'total',
      header: 'Total',
      sortField: 'grand_total',
      className: 'text-right',
      render: (p) => formatINR(p.grand_total),
    },
    {
      key: 'due',
      header: 'Due',
      sortField: 'balance_due',
      className: 'text-right',
      render: (p) =>
        Number(p.balance_due) > 0 ? (
          <span className="text-red-600">{formatINR(p.balance_due)}</span>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Purchases"
        subtitle="Material bought from suppliers"
        actions={
          <>
            <button className="btn-secondary" onClick={onExport}>
              <Download size={16} /> Export CSV
            </button>
            <Link to="/purchases/new" className="btn-primary">
              <Plus size={16} /> New purchase
            </Link>
          </>
        }
      />
      <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-[1fr_200px_150px_150px_140px_140px]">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="PO, bill no., supplier, item"
        />
        <Select
          value={params.supplier || ''}
          onChange={(e) => setParams({ supplier: e.target.value })}
          placeholder="All suppliers"
          options={suppliers.map((s) => ({ value: s.id, label: s.name }))}
        />
        <Select
          value={params.status || ''}
          onChange={(e) => setParams({ status: e.target.value })}
          placeholder="Goods: all"
          options={[
            { value: 'ORDERED', label: 'Ordered' },
            { value: 'PARTIAL', label: 'Partly received' },
            { value: 'RECEIVED', label: 'Received' },
            { value: 'CANCELLED', label: 'Cancelled' },
          ]}
        />
        <Select
          value={params.payment_status || ''}
          onChange={(e) => setParams({ payment_status: e.target.value })}
          placeholder="Payment: all"
          options={[
            { value: 'UNPAID', label: 'Unpaid' },
            { value: 'PARTIAL', label: 'Part paid' },
            { value: 'PAID', label: 'Paid' },
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
        onRowClick={(p) => navigate(`/purchases/${p.id}`)}
        emptyText="No purchases match."
      />
    </>
  );
}
