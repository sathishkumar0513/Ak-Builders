import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Ban, IndianRupee, PackageCheck, Pencil, Printer } from 'lucide-react';
import { purchasesApi, suppliersApi } from '@/api/services';
import { useAuth } from '@/context/AuthContext';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import InfoGrid from '@/components/ui/InfoGrid';
import Badge from '@/components/ui/Badge';
import TotalsPanel from '@/components/lineitems/TotalsPanel';
import { formatDate, formatINR, formatQty } from '@/utils/format';
import { PAYMENT_STATUS, PURCHASE_STATUS } from '@/utils/status';
import ReceiveModal from './ReceiveModal';
import SupplierPaymentModal from '../suppliers/SupplierPaymentModal';

export default function PurchaseDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { hasRole } = useAuth();
  const [receiving, setReceiving] = useState(false);
  const [paying, setPaying] = useState(false);
  const { data: p, isLoading } = useQuery({
    queryKey: ['purchases', id],
    queryFn: () => purchasesApi.get(id),
  });
  const { data: supplier } = useQuery({
    queryKey: ['suppliers', String(p?.supplier)],
    queryFn: () => suppliersApi.get(p.supplier),
    enabled: !!p,
  });
  const refresh = () =>
    ['purchases', 'materials', 'suppliers', 'supplier-payments'].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );
  const cancel = useMutation({
    mutationFn: (reason) => purchasesApi.action(id, 'cancel', { reason }),
    onSuccess: () => {
      toast.success('Purchase cancelled');
      refresh();
    },
  });

  if (isLoading || !p) return <div className="card h-64 animate-pulse" />;
  const hasPending =
    p.items.some((i) => i.material && Number(i.pending_quantity) > 0) && p.status !== 'CANCELLED';

  return (
    <>
      <BackLink to="/purchases">All purchases</BackLink>
      <PageHeader
        title={p.po_number}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <Link to={`/suppliers/${p.supplier}`} className="hover:underline">
              {p.supplier_name}
            </Link>{' '}
            · {formatDate(p.purchase_date)}
            <Badge color={PURCHASE_STATUS[p.status]}>{p.status_display}</Badge>
            {p.status !== 'CANCELLED' && (
              <Badge color={PAYMENT_STATUS[p.payment_status]}>{p.payment_status_display}</Badge>
            )}
          </span>
        }
        actions={
          <>
            {hasPending && (
              <button className="btn-primary" onClick={() => setReceiving(true)}>
                <PackageCheck size={16} /> Receive goods
              </button>
            )}
            {p.status !== 'CANCELLED' && Number(p.balance_due) > 0 && (
              <button className="btn-secondary" onClick={() => setPaying(true)}>
                <IndianRupee size={16} /> Record payment
              </button>
            )}
            {p.can_edit && (
              <Link to={`/purchases/${id}/edit`} className="btn-secondary">
                <Pencil size={16} /> Edit
              </Link>
            )}
            <button className="btn-secondary" onClick={() => window.print()}>
              <Printer size={16} /> Print
            </button>
            {hasRole('ADMIN') && p.can_edit && Number(p.amount_paid) === 0 && (
              <button
                className="btn-ghost text-red-600"
                onClick={async () => {
                  if (
                    await confirm({
                      title: 'Cancel purchase?',
                      message: `${p.po_number} will be marked cancelled. This cannot be undone.`,
                      confirmText: 'Cancel purchase',
                      danger: true,
                    })
                  )
                    cancel.mutate('Cancelled from app');
                }}
              >
                <Ban size={16} /> Cancel
              </button>
            )}
          </>
        }
      />
      <div className="card mb-4">
        <InfoGrid
          items={[
            ['Supplier bill no.', p.supplier_invoice_number],
            ['Bill date', formatDate(p.supplier_invoice_date)],
            ['Tax type', p.is_interstate ? 'IGST (inter-state)' : 'CGST + SGST'],
            ['Supplier GSTIN', supplier?.gstin],
            ['Project', p.project_name],
            ['Notes', p.notes],
          ]}
        />
      </div>
      <div className="card mb-4 overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900/40">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="text-left">Item</th>
              <th className="text-left">HSN</th>
              <th className="text-right">Qty</th>
              <th className="text-right">Rate</th>
              <th className="text-right">Disc</th>
              <th className="text-right">Taxable</th>
              <th className="text-right">GST</th>
              <th className="text-right">Total</th>
              <th className="px-3 text-right">Received</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {p.items.map((i, n) => (
              <tr key={i.id}>
                <td className="px-3 py-2">{n + 1}</td>
                <td>{i.description}</td>
                <td className="text-xs">{i.hsn_code}</td>
                <td className="text-right">
                  {formatQty(i.quantity)} {i.unit}
                </td>
                <td className="text-right">{formatINR(i.rate)}</td>
                <td className="text-right">
                  {Number(i.discount_percent) ? `${Number(i.discount_percent)}%` : '—'}
                </td>
                <td className="text-right">{formatINR(i.taxable_amount)}</td>
                <td className="text-right">{Number(i.gst_rate)}%</td>
                <td className="text-right font-medium">{formatINR(i.line_total)}</td>
                <td className="px-3 text-right">
                  {i.material ? (
                    <span
                      className={
                        Number(i.pending_quantity) > 0 ? 'text-amber-600' : 'text-green-700'
                      }
                    >
                      {formatQty(i.received_quantity)}/{formatQty(i.quantity)}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">service</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="card">
          <h2 className="mb-2 font-semibold">Payments</h2>
          {p.payments.length === 0 ? (
            <p className="text-sm text-slate-500">No payments yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
              {p.payments.map((pay) => (
                <li key={pay.id} className="flex justify-between py-2">
                  <span>
                    {pay.voucher_number} · {formatDate(pay.date)} · {pay.mode_display}
                    {pay.reference_number && ` · ${pay.reference_number}`}
                  </span>
                  <span className="font-medium">{formatINR(pay.amount)}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex justify-between border-t border-slate-200 pt-2 text-sm dark:border-slate-700">
            <span>Paid {formatINR(p.amount_paid)}</span>
            <span
              className={
                Number(p.balance_due) > 0 ? 'font-semibold text-red-600' : 'text-green-700'
              }
            >
              Balance {formatINR(p.balance_due)}
            </span>
          </div>
        </div>
        <TotalsPanel doc={p} interstate={p.is_interstate} />
      </div>
      <ReceiveModal
        purchase={p}
        open={receiving}
        onClose={() => setReceiving(false)}
        onSaved={refresh}
      />
      {supplier && (
        <SupplierPaymentModal
          open={paying}
          supplier={supplier}
          purchase={p}
          onClose={() => setPaying(false)}
          onSaved={refresh}
        />
      )}
    </>
  );
}
