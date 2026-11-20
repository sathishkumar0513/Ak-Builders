import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Ban, BellRing, IndianRupee, Mail, Pencil } from 'lucide-react';
import { adjustmentsApi, invoicesApi } from '@/api/services';
import { api, getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import Badge from '@/components/ui/Badge';
import InfoGrid from '@/components/ui/InfoGrid';
import Modal from '@/components/ui/Modal';
import Spinner from '@/components/ui/Spinner';
import { Field, Input, Textarea } from '@/components/ui/Field';
import TotalsPanel from '@/components/lineitems/TotalsPanel';
import DocumentButtons from '@/components/DocumentButtons';
import { shareToWhatsApp } from '@/utils/documents';
import { formatDate, formatINR, formatQty } from '@/utils/format';
import { CHEQUE_STATUS, INVOICE_STATUS } from '@/utils/status';
import PaymentModal from '../payments/PaymentModal';
import ReasonModal from '../payments/ReasonModal';

function EmailModal({ inv, open, onClose }) {
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    api
      .get(`/invoices/${inv.id}/share-text/`)
      .then(({ data }) =>
        setF({ to: data.email || '', subject: `Invoice ${inv.number}`, message: data.message }),
      );
  }, [open, inv.id, inv.number]);
  const close = () => {
    setF(null);
    onClose();
  };
  const send = async () => {
    setBusy(true);
    try {
      await invoicesApi.action(inv.id, 'email', {
        to: f.to.split(/[,;\s]+/).filter(Boolean),
        subject: f.subject,
        message: f.message,
      });
      toast.success('Invoice emailed with PDF attached');
      close();
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={close}
      title="Email invoice"
      size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={close}>
            Cancel
          </button>
          <button className="btn-primary" onClick={send} disabled={busy || !f?.to}>
            {busy && <Spinner />} Send
          </button>
        </>
      }
    >
      {!f ? (
        <Spinner />
      ) : (
        <div className="space-y-3">
          <Field label="To">
            <Input value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} />
          </Field>
          <Field label="Subject">
            <Input value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} />
          </Field>
          <Field label="Message">
            <Textarea
              rows={8}
              value={f.message}
              onChange={(e) => setF({ ...f, message: e.target.value })}
            />
          </Field>
        </div>
      )}
    </Modal>
  );
}

export default function InvoiceDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const [modal, setModal] = useState(null);
  const [reminding, setReminding] = useState(false);
  const { data: inv, isLoading } = useQuery({
    queryKey: ['invoices', id],
    queryFn: () => invoicesApi.get(id),
  });
  const refresh = () =>
    ['invoices', 'payments', 'advances', 'customers', 'projects'].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );

  if (isLoading || !inv) return <div className="card h-64 animate-pulse" />;
  const active = inv.status !== 'CANCELLED';
  const due = active && Number(inv.balance_due) > 0;

  const remind = async () => {
    setReminding(true);
    try {
      const { data } = await api.get(`/invoices/${inv.id}/share-text/?reminder=1`);
      const r = await shareToWhatsApp({
        pdfUrl: `/invoices/${inv.id}/pdf/`,
        filename: data.filename,
        message: data.message,
        phone: data.phone,
      });
      if (r && r !== 'cancelled') {
        await invoicesApi.action(inv.id, 'log-reminder', { channel: 'WHATSAPP' });
        toast.success('Reminder sent and logged');
      }
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setReminding(false);
    }
  };
  const removeAdj = async (adjId) => {
    try {
      await adjustmentsApi.remove(adjId);
      toast.success('Adjustment removed');
      refresh();
    } catch (e) {
      toast.error(getErrorMessage(e));
    }
  };

  return (
    <>
      <BackLink to="/invoices">All invoices</BackLink>
      <PageHeader
        title={inv.number}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <Link to={`/customers/${inv.customer}`} className="hover:underline">
              {inv.billing_name}
            </Link>{' '}
            · {formatDate(inv.invoice_date)}
            <Badge color={INVOICE_STATUS[inv.status]}>{inv.status_display}</Badge>
            {inv.is_overdue && <Badge color="red">Overdue</Badge>}
          </span>
        }
        actions={
          <>
            {due && (
              <button className="btn-primary" onClick={() => setModal('pay')}>
                <IndianRupee size={16} /> Record payment
              </button>
            )}
            {due && inv.is_overdue && (
              <button className="btn-secondary" onClick={remind} disabled={reminding}>
                {reminding ? <Spinner /> : <BellRing size={16} />} Reminder
              </button>
            )}
            <DocumentButtons base={`/invoices/${inv.id}/`} />
            <button className="btn-secondary px-2" title="Email" onClick={() => setModal('email')}>
              <Mail size={16} />
            </button>
            {inv.can_edit && (
              <Link to={`/invoices/${inv.id}/edit`} className="btn-secondary px-2" title="Edit">
                <Pencil size={16} />
              </Link>
            )}
            {hasRole('ADMIN') && active && (
              <button className="btn-ghost text-red-600" onClick={() => setModal('cancel')}>
                <Ban size={16} /> Cancel
              </button>
            )}
          </>
        }
      />
      {!active && (
        <div className="mb-3 rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800">
          Cancelled: {inv.cancelled_reason}
        </div>
      )}
      <div className="card mb-4">
        <InfoGrid
          items={[
            ['Due date', formatDate(inv.due_date)],
            [
              'Project',
              inv.project_detail && (
                <Link
                  className="text-brand-700 hover:underline"
                  to={`/projects/${inv.project_detail.id}`}
                >
                  {inv.project_detail.code}
                </Link>
              ),
            ],
            ['Stage', inv.stage_name],
            [
              'Quotation',
              inv.quotation && (
                <Link
                  className="text-brand-700 hover:underline"
                  to={`/quotations/${inv.quotation}`}
                >
                  {inv.quotation_number}
                </Link>
              ),
            ],
            ['Billing address', inv.billing_address],
            ['GSTIN', inv.billing_gstin || 'Unregistered (B2C)'],
            ['Tax', inv.is_interstate ? 'IGST' : 'CGST + SGST'],
            ['Stock', inv.deduct_stock ? 'Deducted from store' : '—'],
          ]}
        />
      </div>
      <div className="card mb-4 overflow-x-auto p-0">
        <table className="w-full min-w-[700px] text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900/40">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="text-left">Description</th>
              <th className="text-left">HSN/SAC</th>
              <th className="text-right">Qty</th>
              <th className="text-right">Rate</th>
              <th className="text-right">Taxable</th>
              <th className="text-right">GST</th>
              <th className="px-3 text-right">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {inv.items.map((i, n) => (
              <tr key={i.id}>
                <td className="px-3 py-2">{n + 1}</td>
                <td>{i.description}</td>
                <td className="text-xs">{i.hsn_code}</td>
                <td className="text-right">
                  {formatQty(i.quantity)} {i.unit_display}
                </td>
                <td className="text-right">{formatINR(i.rate)}</td>
                <td className="text-right">{formatINR(i.taxable_amount)}</td>
                <td className="text-right">{Number(i.gst_rate)}%</td>
                <td className="px-3 text-right font-medium">{formatINR(i.line_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="card text-sm">
          <h2 className="mb-2 font-semibold">Settlement</h2>
          <ul className="divide-y divide-slate-100 dark:divide-slate-700">
            {inv.adjustments.map((a) => (
              <li key={`a${a.id}`} className="flex items-center justify-between py-2">
                <span>
                  Advance{' '}
                  <Link to={`/advances/${a.advance}`} className="text-brand-700 hover:underline">
                    {a.receipt_number}
                  </Link>{' '}
                  adjusted · {formatDate(a.date)}
                </span>
                <span className="flex items-center gap-2 font-medium">
                  {formatINR(a.amount)}
                  {hasRole('ADMIN') && active && (
                    <button
                      className="btn-ghost px-1 text-xs text-red-600"
                      onClick={() => removeAdj(a.id)}
                    >
                      Undo
                    </button>
                  )}
                </span>
              </li>
            ))}
            {inv.payments.map((p) => (
              <li key={`p${p.id}`} className="flex items-center justify-between py-2">
                <span>
                  Receipt {p.receipt_number} · {formatDate(p.date)} · {p.mode}
                  {p.reference_number && ` · ${p.reference_number}`}{' '}
                  {p.cheque_status !== 'NA' && (
                    <Badge color={CHEQUE_STATUS[p.cheque_status]}>
                      {p.cheque_status.toLowerCase()}
                    </Badge>
                  )}
                </span>
                <span
                  className={`font-medium ${p.cheque_status === 'BOUNCED' ? 'text-red-600 line-through' : ''}`}
                >
                  {formatINR(p.amount)}
                </span>
              </li>
            ))}
            {inv.adjustments.length + inv.payments.length === 0 && (
              <li className="py-2 text-slate-500">Nothing received yet.</li>
            )}
          </ul>
          <div className="mt-3 grid grid-cols-3 gap-2 border-t border-slate-200 pt-3 text-center dark:border-slate-700">
            <div>
              <p className="text-xs text-slate-500">Advance adjusted</p>
              <p className="font-semibold">{formatINR(inv.advance_adjusted)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Paid</p>
              <p className="font-semibold">{formatINR(inv.amount_paid)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Balance due</p>
              <p className={`font-semibold ${due ? 'text-red-600' : 'text-green-700'}`}>
                {formatINR(inv.balance_due)}
              </p>
            </div>
          </div>
        </div>
        <TotalsPanel doc={{ ...inv, transport_charges: 0 }} interstate={inv.is_interstate} />
      </div>
      <PaymentModal
        open={modal === 'pay'}
        onClose={() => setModal(null)}
        customerId={inv.customer}
        invoiceId={inv.id}
        onSaved={refresh}
      />
      <EmailModal inv={inv} open={modal === 'email'} onClose={() => setModal(null)} />
      <ReasonModal
        open={modal === 'cancel'}
        onClose={() => setModal(null)}
        title={`Cancel invoice ${inv.number}?`}
        description="Allowed only when no payment is recorded. Adjusted advances go back to the customer's advance balance and the ledger gets a reversal entry. The number is not reused."
        confirmText="Cancel invoice"
        onConfirm={async (reason) => {
          await invoicesApi.action(inv.id, 'cancel', { reason });
          toast.success('Invoice cancelled');
          refresh();
        }}
      />
    </>
  );
}
