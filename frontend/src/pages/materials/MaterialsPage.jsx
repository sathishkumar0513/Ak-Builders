import { useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Download, Plus, Tags } from 'lucide-react';
import { categoriesApi, materialsApi } from '@/api/services';
import { useAuth } from '@/context/AuthContext';
import { useListParams } from '@/hooks/useListParams';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Select } from '@/components/ui/Field';
import { exportCsv } from '@/utils/exportCsv';
import { formatINR, formatQty } from '@/utils/format';
import MaterialFormModal from './MaterialFormModal';
import CategoriesModal from './CategoriesModal';

export default function MaterialsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const canEdit = hasRole('ADMIN', 'ACCOUNTANT');
  const seeCost = canEdit;
  const { params, setParams, toggleOrdering } = useListParams({
    ordering: 'category__name',
    is_active: 'true',
  });
  const [editing, setEditing] = useState(null);
  const [catsOpen, setCatsOpen] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ['materials', params],
    queryFn: () => materialsApi.list(params),
    placeholderData: keepPreviousData,
  });
  const { data: cats = [] } = useQuery({
    queryKey: ['material-categories'],
    queryFn: () => categoriesApi.list(),
  });
  const { data: low } = useQuery({
    queryKey: ['materials', 'low-stock'],
    queryFn: () => materialsApi.collection('low-stock'),
  });

  const onExport = async () => {
    const all = await materialsApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-materials',
      [
        { header: 'Category', value: (m) => m.category_name },
        { header: 'Material', value: (m) => m.name },
        { header: 'Brand', value: (m) => m.brand },
        { header: 'HSN', value: (m) => m.hsn_code },
        { header: 'Unit', value: (m) => m.unit },
        ...(seeCost ? [{ header: 'Purchase price', value: (m) => m.purchase_price }] : []),
        { header: 'Selling price', value: (m) => m.selling_price },
        { header: 'GST %', value: (m) => m.gst_rate },
        { header: 'Stock', value: (m) => m.stock_quantity },
        { header: 'Reorder level', value: (m) => m.reorder_level },
        ...(seeCost ? [{ header: 'Stock value', value: (m) => m.stock_value }] : []),
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'name',
      header: 'Material',
      sortField: 'name',
      render: (m) => (
        <div>
          <p className="font-medium">
            {m.name} {!m.is_active && <Badge color="gray">Inactive</Badge>}
          </p>
          <p className="text-xs text-slate-500">
            {[m.brand, m.category_name, m.hsn_code && `HSN ${m.hsn_code}`]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
      ),
    },
    {
      key: 'stock',
      header: 'Stock',
      sortField: 'stock_quantity',
      className: 'text-right',
      render: (m) => (
        <span className={m.is_low_stock ? 'font-semibold text-red-600' : ''}>
          {formatQty(m.stock_quantity)} {m.unit}
          {m.is_low_stock && <AlertTriangle size={13} className="ml-1 inline" />}
        </span>
      ),
    },
    ...(seeCost
      ? [
          {
            key: 'pp',
            header: 'Purchase',
            sortField: 'purchase_price',
            className: 'text-right',
            render: (m) => formatINR(m.purchase_price),
          },
        ]
      : []),
    {
      key: 'sp',
      header: 'Selling',
      sortField: 'selling_price',
      className: 'text-right',
      render: (m) => `${formatINR(m.selling_price)}/${m.unit}`,
    },
    {
      key: 'gst',
      header: 'GST',
      className: 'text-right',
      mobileHidden: true,
      render: (m) => `${Number(m.gst_rate)}%`,
    },
    ...(seeCost
      ? [
          {
            key: 'value',
            header: 'Stock value',
            className: 'text-right',
            mobileHidden: true,
            render: (m) => formatINR(m.stock_value),
          },
        ]
      : []),
  ];

  return (
    <>
      <PageHeader
        title="Materials & stock"
        subtitle={data ? `${data.count} materials` : ' '}
        actions={
          <>
            <button className="btn-secondary" onClick={() => setCatsOpen(true)}>
              <Tags size={16} /> Categories
            </button>
            <button className="btn-secondary" onClick={onExport}>
              <Download size={16} /> Export CSV
            </button>
            {canEdit && (
              <button className="btn-primary" onClick={() => setEditing({})}>
                <Plus size={16} /> Add material
              </button>
            )}
          </>
        }
      />
      {low?.count > 0 && params.low_stock !== 'true' && (
        <button
          onClick={() => setParams({ low_stock: 'true' })}
          className="mb-3 flex w-full items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-left text-sm text-red-800 hover:bg-red-100 dark:border-red-800 dark:bg-red-900/30 dark:text-red-200"
        >
          <AlertTriangle size={16} /> <b>{low.count}</b> material{low.count > 1 ? 's are' : ' is'}{' '}
          at or below reorder level — click to view
        </button>
      )}
      <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_180px_160px_150px]">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Search name, brand, HSN"
        />
        <Select
          value={params.category || ''}
          onChange={(e) => setParams({ category: e.target.value })}
          placeholder="All categories"
          options={cats.map((c) => ({ value: c.id, label: `${c.name} (${c.material_count})` }))}
        />
        <Select
          value={params.low_stock || ''}
          onChange={(e) => setParams({ low_stock: e.target.value })}
          placeholder="All stock levels"
          options={[
            { value: 'true', label: 'Low stock only' },
            { value: 'false', label: 'Stock OK' },
          ]}
        />
        <Select
          value={params.is_active ?? ''}
          onChange={(e) => setParams({ is_active: e.target.value })}
          placeholder="Active + inactive"
          options={[
            { value: 'true', label: 'Active' },
            { value: 'false', label: 'Inactive' },
          ]}
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
        onRowClick={(m) => navigate(`/materials/${m.id}`)}
      />
      <MaterialFormModal
        material={editing}
        onClose={() => setEditing(null)}
        onSaved={() => qc.invalidateQueries({ queryKey: ['materials'] })}
      />
      <CategoriesModal
        open={catsOpen}
        onClose={() => setCatsOpen(false)}
        canEdit={hasRole('ADMIN')}
      />
    </>
  );
}
