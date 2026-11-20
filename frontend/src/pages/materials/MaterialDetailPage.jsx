import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { AlertTriangle, Pencil, SlidersHorizontal, Trash2 } from 'lucide-react';
import { materialsApi } from '@/api/services';
import { useAuth } from '@/context/AuthContext';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import StatCard from '@/components/ui/StatCard';
import InfoGrid from '@/components/ui/InfoGrid';
import Tabs from '@/components/ui/Tabs';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import { formatDate, formatDateTime, formatINR, formatQty } from '@/utils/format';
import { INWARD, MOVEMENT_COLOR } from '@/utils/status';
import MaterialFormModal from './MaterialFormModal';
import StockAdjustModal from './StockAdjustModal';

export default function MaterialDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { hasRole } = useAuth();
  const canEdit = hasRole('ADMIN', 'ACCOUNTANT');
  const [tab, setTab] = useState('movements');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [adjusting, setAdjusting] = useState(false);
  const { data: m, isLoading } = useQuery({
    queryKey: ['materials', id],
    queryFn: () => materialsApi.get(id),
  });
  const { data: moves, isLoading: movesLoading } = useQuery({
    queryKey: ['materials', id, 'movements', page],
    queryFn: () => materialsApi.detail(id, 'movements', { page }),
    placeholderData: keepPreviousData,
  });
  const { data: prices = [] } = useQuery({
    queryKey: ['materials', id, 'prices'],
    queryFn: () => materialsApi.detail(id, 'price-history'),
    enabled: canEdit,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ['materials'] });
  const del = useMutation({
    mutationFn: () => materialsApi.remove(id),
    onSuccess: () => {
      toast.success('Material deleted');
      refresh();
      navigate('/materials');
    },
  });

  if (isLoading || !m) return <div className="card h-64 animate-pulse" />;

  const moveCols = [
    { key: 'date', header: 'Date', render: (r) => formatDate(r.date) },
    {
      key: 'type',
      header: 'Type',
      render: (r) => (
        <Badge color={MOVEMENT_COLOR[r.movement_type]}>{r.movement_type_display}</Badge>
      ),
    },
    {
      key: 'qty',
      header: 'Qty',
      className: 'text-right',
      render: (r) => (
        <span className={INWARD.has(r.movement_type) ? 'text-green-700' : 'text-red-600'}>
          {INWARD.has(r.movement_type) ? '+' : '−'}
          {formatQty(r.quantity)}
        </span>
      ),
    },
    {
      key: 'bal',
      header: 'Balance',
      className: 'text-right',
      render: (r) => formatQty(r.balance_after),
    },
    {
      key: 'ref',
      header: 'Reference',
      render: (r) => (
        <span className="text-xs">{r.project_name || r.note || r.reference_type}</span>
      ),
    },
    {
      key: 'by',
      header: 'By',
      mobileHidden: true,
      render: (r) => <span className="text-xs text-slate-500">{r.created_by_name}</span>,
    },
  ];
  const priceCols = [
    { key: 'when', header: 'Changed', render: (r) => formatDateTime(r.changed_at) },
    {
      key: 'pp',
      header: 'Purchase',
      render: (r) => `${formatINR(r.old_purchase_price)} → ${formatINR(r.new_purchase_price)}`,
    },
    {
      key: 'sp',
      header: 'Selling',
      render: (r) => `${formatINR(r.old_selling_price)} → ${formatINR(r.new_selling_price)}`,
    },
    { key: 'reason', header: 'Reason', render: (r) => r.reason },
    { key: 'by', header: 'By', mobileHidden: true, render: (r) => r.changed_by_name },
  ];

  return (
    <>
      <BackLink to="/materials">All materials</BackLink>
      <PageHeader
        title={`${m.name} ${m.brand}`.trim()}
        subtitle={`${m.category_name}${m.hsn_code ? ` · HSN ${m.hsn_code}` : ''} · per ${m.unit_display}`}
        actions={
          <>
            {hasRole('ADMIN') && (
              <button className="btn-secondary" onClick={() => setAdjusting(true)}>
                <SlidersHorizontal size={16} /> Adjust stock
              </button>
            )}
            {canEdit && (
              <button className="btn-secondary" onClick={() => setEditing(m)}>
                <Pencil size={16} /> Edit
              </button>
            )}
            {hasRole('ADMIN') && (
              <button
                className="btn-ghost text-red-600"
                title="Delete"
                onClick={async () => {
                  if (
                    await confirm({
                      title: 'Delete material?',
                      message: 'Only possible when stock is zero. Past records stay.',
                      confirmText: 'Delete',
                      danger: true,
                    })
                  )
                    del.mutate();
                }}
              >
                <Trash2 size={16} />
              </button>
            )}
          </>
        }
      />
      {m.is_low_stock && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/30 dark:text-red-200">
          <AlertTriangle size={16} /> Stock is at or below the reorder level (
          {formatQty(m.reorder_level)} {m.unit}). Time to reorder.
        </div>
      )}
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="In stock"
          value={`${formatQty(m.stock_quantity)} ${m.unit}`}
          hint={`Reorder at ${formatQty(m.reorder_level)}`}
        />
        <StatCard
          label="Selling price"
          value={formatINR(m.selling_price)}
          hint={`+ ${Number(m.gst_rate)}% GST`}
        />
        {m.purchase_price !== undefined && (
          <StatCard
            label="Purchase price"
            value={formatINR(m.purchase_price)}
            hint="Latest net cost"
          />
        )}
        {m.stock_value !== undefined && (
          <StatCard label="Stock value" value={formatINR(m.stock_value)} hint="At purchase price" />
        )}
      </div>
      {m.description && (
        <div className="card mb-4">
          <InfoGrid
            items={[
              ['Description', m.description],
              ['SKU', m.sku],
            ]}
          />
        </div>
      )}
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: 'movements', label: 'Stock history', count: moves?.count },
          ...(canEdit ? [{ id: 'prices', label: 'Price history', count: prices.length }] : []),
        ]}
      />
      {tab === 'movements' ? (
        <DataTable
          columns={moveCols}
          rows={moves?.results}
          loading={movesLoading}
          page={page}
          totalPages={moves?.total_pages}
          count={moves?.count}
          pageSize={20}
          onPageChange={setPage}
          emptyText="No stock movements yet."
        />
      ) : (
        <DataTable columns={priceCols} rows={prices} emptyText="No price changes recorded yet." />
      )}
      <MaterialFormModal material={editing} onClose={() => setEditing(null)} onSaved={refresh} />
      <StockAdjustModal
        material={m}
        open={adjusting}
        onClose={() => setAdjusting(false)}
        onSaved={refresh}
      />
    </>
  );
}
