import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Download, Plus } from 'lucide-react';
import { suppliersApi } from '@/api/services';
import { useListParams } from '@/hooks/useListParams';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import { exportCsv } from '@/utils/exportCsv';
import { formatINR } from '@/utils/format';
import SupplierFormModal from './SupplierFormModal';

export default function SuppliersPage() {
  const navigate = useNavigate();
  const { params, setParams, toggleOrdering } = useListParams({ ordering: 'name' });
  const [editing, setEditing] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ['suppliers', params],
    queryFn: () => suppliersApi.list(params),
    placeholderData: keepPreviousData,
  });
  const totalPayable = (data?.results || []).reduce((s, x) => s + Number(x.payable), 0);

  const onExport = async () => {
    const all = await suppliersApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-suppliers',
      [
        { header: 'Supplier', value: (s) => s.name },
        { header: 'Contact', value: (s) => s.contact_person },
        { header: 'Mobile', value: (s) => s.phone },
        { header: 'City', value: (s) => s.city },
        { header: 'State', value: (s) => s.state_name },
        { header: 'GSTIN', value: (s) => s.gstin },
        { header: 'Total purchases', value: (s) => s.total_purchases },
        { header: 'Paid', value: (s) => s.total_paid },
        { header: 'Payable', value: (s) => s.payable },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'name',
      header: 'Supplier',
      sortField: 'name',
      render: (s) => (
        <div>
          <p className="font-medium">{s.name}</p>
          <p className="text-xs text-slate-500">{s.contact_person}</p>
        </div>
      ),
    },
    { key: 'phone', header: 'Mobile', render: (s) => s.phone },
    {
      key: 'city',
      header: 'City',
      sortField: 'city',
      render: (s) =>
        [s.city, s.state_code !== '33' && s.state_name].filter(Boolean).join(', ') || '—',
    },
    {
      key: 'gstin',
      header: 'GSTIN',
      mobileHidden: true,
      render: (s) => <span className="font-mono text-xs">{s.gstin || '—'}</span>,
    },
    {
      key: 'purchases',
      header: 'Purchases',
      sortField: 'total_purchases',
      className: 'text-right',
      render: (s) => formatINR(s.total_purchases),
    },
    {
      key: 'payable',
      header: 'Payable',
      sortField: 'payable',
      className: 'text-right',
      render: (s) =>
        Number(s.payable) > 0 ? (
          <span className="font-medium text-red-600">{formatINR(s.payable)}</span>
        ) : (
          <span className="text-slate-400">—</span>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Suppliers"
        subtitle={
          data ? `${data.count} suppliers · ${formatINR(totalPayable)} payable on this page` : ' '
        }
        actions={
          <>
            <button className="btn-secondary" onClick={onExport}>
              <Download size={16} /> Export CSV
            </button>
            <button className="btn-primary" onClick={() => setEditing({})}>
              <Plus size={16} /> Add supplier
            </button>
          </>
        }
      />
      <div className="mb-3">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Search name, mobile, GSTIN, city"
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
        onRowClick={(s) => navigate(`/suppliers/${s.id}`)}
        emptyText="No suppliers yet."
      />
      <SupplierFormModal
        supplier={editing}
        onClose={() => setEditing(null)}
        onSaved={(s) => navigate(`/suppliers/${s.id}`)}
      />
    </>
  );
}
