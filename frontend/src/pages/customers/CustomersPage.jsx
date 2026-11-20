import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Download, Phone, Plus } from 'lucide-react';
import { customersApi } from '@/api/services';
import { useListParams } from '@/hooks/useListParams';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Select } from '@/components/ui/Field';
import SearchSelect from '@/components/ui/SearchSelect';
import { exportCsv } from '@/utils/exportCsv';
import { formatINR } from '@/utils/format';
import CustomerFormModal from './CustomerFormModal';

const outstandingCell = (v) => {
  const n = Number(v || 0);
  if (n === 0) return <span className="text-slate-400">—</span>;
  return n > 0 ? (
    <span className="font-medium text-red-600">{formatINR(n)}</span>
  ) : (
    <span className="text-green-700">Advance {formatINR(-n)}</span>
  );
};

export default function CustomersPage() {
  const navigate = useNavigate();
  const { params, setParams, toggleOrdering } = useListParams({ ordering: 'name' });
  const [editing, setEditing] = useState(null);
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['customers', params],
    queryFn: () => customersApi.list(params),
    placeholderData: keepPreviousData,
  });
  const { data: cities = [] } = useQuery({
    queryKey: ['customers', 'cities'],
    queryFn: () => customersApi.collection('cities'),
  });

  const onExport = async () => {
    const all = await customersApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-customers',
      [
        { header: 'Name', value: (c) => c.name },
        { header: 'Type', value: (c) => c.customer_type_display },
        { header: 'Mobile', value: (c) => c.phone },
        { header: 'Alternate', value: (c) => c.alternate_phone },
        { header: 'Email', value: (c) => c.email },
        { header: 'Address', value: (c) => c.address },
        { header: 'City', value: (c) => c.city },
        { header: 'Pincode', value: (c) => c.pincode },
        { header: 'State', value: (c) => c.state_name },
        { header: 'GSTIN', value: (c) => c.gstin },
        { header: 'Outstanding', value: (c) => c.outstanding },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'name',
      header: 'Customer',
      sortField: 'name',
      render: (c) => (
        <div>
          <p className="font-medium">{c.name}</p>
          {c.contact_person && <p className="text-xs text-slate-500">{c.contact_person}</p>}
        </div>
      ),
    },
    {
      key: 'phone',
      header: 'Mobile',
      render: (c) => (
        <a
          href={`tel:${c.phone}`}
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1 text-brand-700 hover:underline"
        >
          <Phone size={13} /> {c.phone}
        </a>
      ),
    },
    { key: 'city', header: 'City', sortField: 'city', render: (c) => c.city || '—' },
    {
      key: 'type',
      header: 'Type',
      mobileHidden: true,
      render: (c) => (
        <Badge color={c.customer_type === 'COMPANY' ? 'blue' : 'gray'}>
          {c.customer_type_display}
        </Badge>
      ),
    },
    {
      key: 'gstin',
      header: 'GSTIN',
      mobileHidden: true,
      render: (c) => <span className="font-mono text-xs">{c.gstin || '—'}</span>,
    },
    {
      key: 'outstanding',
      header: 'Outstanding',
      sortField: 'outstanding',
      className: 'text-right',
      render: (c) => outstandingCell(c.outstanding),
    },
  ];

  return (
    <>
      <PageHeader
        title="Customers"
        subtitle={data ? `${data.count} customers` : ' '}
        actions={
          <>
            <button className="btn-secondary" onClick={onExport}>
              <Download size={16} /> Export CSV
            </button>
            <button className="btn-primary" onClick={() => setEditing({})}>
              <Plus size={16} /> Add customer
            </button>
          </>
        }
      />
      <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_180px_180px]">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Search name, mobile, GSTIN, city"
        />
        <Select
          value={params.customer_type || ''}
          onChange={(e) => setParams({ customer_type: e.target.value })}
          placeholder="All types"
          options={[
            { value: 'INDIVIDUAL', label: 'Individual' },
            { value: 'COMPANY', label: 'Company' },
          ]}
        />
        <SearchSelect
          value={params.city || ''}
          onChange={(v) => setParams({ city: v })}
          placeholder="All cities"
          emptyText="No customers in that city"
          clearable
          options={cities.map((c) => ({ value: c, label: c }))}
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
        onRowClick={(c) => navigate(`/customers/${c.id}`)}
        emptyText="No customers yet. Click 'Add customer' to create one."
      />
      <CustomerFormModal
        customer={editing}
        onClose={() => setEditing(null)}
        onSaved={(c) => (editing?.id ? refetch() : navigate(`/customers/${c.id}`))}
      />
    </>
  );
}
