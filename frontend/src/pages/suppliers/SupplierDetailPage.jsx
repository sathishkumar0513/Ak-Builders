import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { IndianRupee, Pencil, Phone, Plus, Trash2, XCircle } from 'lucide-react';
import { purchasesApi, supplierPaymentsApi, suppliersApi } from '@/api/services';
import { useAuth } from '@/context/AuthContext';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import StatCard from '@/components/ui/StatCard';
import InfoGrid from '@/components/ui/InfoGrid';
import Tabs from '@/components/ui/Tabs';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import { formatDate, formatINR } from '@/utils/format';
import { PAYMENT_STATUS, PURCHASE_STATUS } from '@/utils/status';
import SupplierFormModal from './SupplierFormModal';
import SupplierPaymentModal from './SupplierPaymentModal';

export default function SupplierDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { hasRole } = useAuth();
  const [tab, setTab] = useState('purchases');
  const [editing, setEditing] = useState(null);
  const [paying, setPaying] = useState(false);
  const { data: s } = useQuery({
    queryKey: ['suppliers', id],
    queryFn: () => suppliersApi.get(id),
  });
  const { data: purchases } = useQuery({
    queryKey: ['purchases', { supplier: id }],
    queryFn: () => purchasesApi.list({ supplier: id, page_size: 200 }),
  });
  const { data: payments } = useQuery({
    queryKey: ['supplier-payments', { supplier: id }],
    queryFn: () => supplierPaymentsApi.list({ supplier: id, page_size: 200 }),
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['suppliers'] });
    qc.invalidateQueries({ queryKey: ['purchases'] });
    qc.invalidateQueries({ queryKey: ['supplier-payments'] });
  };
  const cancelPay = useMutation({
    mutationFn: (pid) => supplierPaymentsApi.remove(pid),
    onSuccess: () => {
      toast.success('Payment cancelled');
      refresh();
    },
  });
  const del = useMutation({
    mutationFn: () => suppliersApi.remove(id),
    onSuccess: () => {
      toast.success('Supplier deleted');
      refresh();
      navigate('/suppliers');
    },
  });

  if (!s) return <div className="card h-64 animate-pulse" />;

  return (
    <>
      <BackLink to="/suppliers">All suppliers</BackLink>
      <PageHeader
        title={s.name}
        subtitle={[s.contact_person, s.city, s.state_name].filter(Boolean).join(' · ')}
        actions={
          <>
            <a href={`tel:${s.phone}`} className="btn-secondary">
              <Phone size={16} /> Call
            </a>
            <Link to={`/purchases/new?supplier=${s.id}`} className="btn-secondary">
              <Plus size={16} /> New purchase
            </Link>
            {Number(s.payable) > 0 && (
              <button className="btn-primary" onClick={() => setPaying(true)}>
                <IndianRupee size={16} /> Pay supplier
              </button>
            )}
            <button className="btn-secondary" onClick={() => setEditing(s)}>
              <Pencil size={16} /> Edit
            </button>
            {hasRole('ADMIN') && (
              <button
                className="btn-ghost text-red-600"
                title="Delete"
                onClick={async () => {
                  if (
                    await confirm({
                      title: 'Delete supplier?',
                      message: 'Only possible when nothing is payable.',
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
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatCard
          label="Total purchases"
          value={formatINR(s.total_purchases)}
          hint={Number(s.opening_balance) ? `+ opening ${formatINR(s.opening_balance)}` : undefined}
        />
        <StatCard label="Paid" value={formatINR(s.total_paid)} />
        <StatCard
          label="Payable"
          value={
            <span className={Number(s.payable) > 0 ? 'text-red-600' : ''}>
              {formatINR(s.payable)}
            </span>
          }
        />
      </div>
      <div className="card mb-4">
        <InfoGrid
          items={[
            ['Mobile', s.phone],
            ['Email', s.email],
            ['GSTIN', s.gstin],
            ['Address', s.address],
            ['Bank details', s.bank_details],
            ['Notes', s.notes],
          ]}
        />
      </div>
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: 'purchases', label: 'Purchases', count: purchases?.count },
          { id: 'payments', label: 'Payments', count: payments?.count },
        ]}
      />
      {tab === 'purchases' ? (
        <DataTable
          rows={purchases?.results}
          loading={!purchases}
          onRowClick={(p) => navigate(`/purchases/${p.id}`)}
          emptyText="No purchases yet."
          columns={[
            {
              key: 'po',
              header: 'PO',
              render: (p) => <span className="font-medium">{p.po_number}</span>,
            },
            { key: 'date', header: 'Date', render: (p) => formatDate(p.purchase_date) },
            { key: 'bill', header: 'Bill no.', render: (p) => p.supplier_invoice_number || '—' },
            {
              key: 'status',
              header: 'Status',
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
              className: 'text-right',
              render: (p) => formatINR(p.grand_total),
            },
            {
              key: 'due',
              header: 'Due',
              className: 'text-right',
              render: (p) => formatINR(p.balance_due),
            },
          ]}
        />
      ) : (
        <DataTable
          rows={payments?.results}
          loading={!payments}
          emptyText="No payments yet."
          columns={[
            {
              key: 'v',
              header: 'Voucher',
              render: (p) => <span className="font-medium">{p.voucher_number}</span>,
            },
            { key: 'date', header: 'Date', render: (p) => formatDate(p.date) },
            { key: 'po', header: 'Against', render: (p) => p.po_number || 'On account' },
            {
              key: 'mode',
              header: 'Mode',
              render: (p) =>
                `${p.mode_display}${p.reference_number ? ` · ${p.reference_number}` : ''}`,
            },
            {
              key: 'amt',
              header: 'Amount',
              className: 'text-right',
              render: (p) => formatINR(p.amount),
            },
            {
              key: 'x',
              header: '',
              className: 'text-right',
              render: (p) =>
                hasRole('ADMIN') && (
                  <button
                    className="btn-ghost text-red-600"
                    title="Cancel payment"
                    onClick={async () => {
                      if (
                        await confirm({
                          title: 'Cancel this payment?',
                          message: `${p.voucher_number} for ${formatINR(p.amount)} will be reversed and the balance restored.`,
                          confirmText: 'Cancel payment',
                          danger: true,
                        })
                      )
                        cancelPay.mutate(p.id);
                    }}
                  >
                    <XCircle size={16} />
                  </button>
                ),
            },
          ]}
        />
      )}
      <SupplierFormModal supplier={editing} onClose={() => setEditing(null)} onSaved={refresh} />
      <SupplierPaymentModal
        open={paying}
        supplier={s}
        purchases={purchases?.results || []}
        maxAmount={s.payable}
        onClose={() => setPaying(false)}
        onSaved={refresh}
      />
    </>
  );
}
