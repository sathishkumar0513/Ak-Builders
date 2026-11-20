import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Ban, Link2, Undo2 } from 'lucide-react';
import { adjustmentsApi, advancesApi, customersApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { useLookups } from '@/hooks/useLookups';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import StatCard from '@/components/ui/StatCard';
import InfoGrid from '@/components/ui/InfoGrid';
import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import Spinner from '@/components/ui/Spinner';
import { Field, Input, Select } from '@/components/ui/Field';
import DocumentButtons from '@/components/DocumentButtons';
import { formatDate, formatINR, todayISO } from '@/utils/format';
import { openPdf } from '@/utils/documents';
import { ADVANCE_STATUS } from '@/utils/status';
import ReasonModal from '../payments/ReasonModal';

function AdjustModal({ advance, open, onClose, onDone }) {
  const { data: items } = useQuery({
    queryKey: ['customers', String(advance.customer), 'open-items'],
    queryFn: () => customersApi.detail(advance.customer, 'open-items'),
    enabled: open,
  });
  const [invoice, setInvoice] = useState('');
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const inv = items?.invoices.find((i) => String(i.id) === invoice);
  const max = inv
    ? Math.min(Number(inv.balance_due), Number(advance.balance))
    : Number(advance.balance);
  const save = async () => {
    setBusy(true);
    try {
      await advancesApi.action(advance.id, 'adjust', { invoice: Number(invoice), amount });
      toast.success('Advance adjusted');
      onDone();
      onClose();
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title="Adjust against an invoice"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={save}
            disabled={busy || !invoice || !(Number(amount) > 0) || Number(amount) > max}
          >
            {busy && <Spinner />} Adjust
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <Field
          label="Invoice"
          hint={
            items && items.invoices.length === 0
              ? 'This customer has no unpaid invoices.'
              : undefined
          }
        >
          <Select
            value={invoice}
            placeholder="Select invoice"
            onChange={(e) => {
              setInvoice(e.target.value);
              const i = items.invoices.find((x) => String(x.id) === e.target.value);
              setAmount(i ? String(Math.min(Number(i.balance_due), Number(advance.balance))) : '');
            }}
            options={(items?.invoices || []).map((i) => ({
              value: String(i.id),
              label: `${i.number} · due ${formatINR(i.balance_due)}`,
            }))}
          />
        </Field>
        <Field
          label="Amount (₹)"
          hint={`Up to ${formatINR(max)}`}
          error={Number(amount) > max ? `Max ${formatINR(max)}` : undefined}
        >
          <Input
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </Field>
      </div>
    </Modal>
  );
}

function RefundModal({ advance, open, onClose, onDone }) {
  const { payment_modes } = useLookups();
  const [f, setF] = useState({
    amount: advance.balance,
    date: todayISO(),
    mode: 'BANK',
    reason: '',
    reference_number: '',
  });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    setBusy(true);
    try {
      await advancesApi.action(advance.id, 'refund', f);
      toast.success('Refund recorded');
      onDone();
      onClose();
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title="Refund unused advance"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-danger"
            onClick={save}
            disabled={
              busy ||
              !f.reason ||
              !(Number(f.amount) > 0) ||
              Number(f.amount) > Number(advance.balance)
            }
          >
            {busy && <Spinner />} Record refund
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Amount (₹)" hint={`Unused ${formatINR(advance.balance)}`}>
            <Input type="number" step="0.01" value={f.amount} onChange={set('amount')} />
          </Field>
          <Field label="Date">
            <Input type="date" value={f.date} onChange={set('date')} />
          </Field>
        </div>
        <Field label="Paid back by">
          <Select value={f.mode} onChange={set('mode')} options={payment_modes} />
        </Field>
        <Field label="Reference">
          <Input value={f.reference_number} onChange={set('reference_number')} />
        </Field>
        <Field label="Reason (required)">
          <Input
            value={f.reason}
            onChange={set('reason')}
            placeholder="e.g. Work cancelled by customer"
          />
        </Field>
      </div>
    </Modal>
  );
}

export default function AdvanceDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const [modal, setModal] = useState(null);
  const { data: a, isLoading } = useQuery({
    queryKey: ['advances', id],
    queryFn: () => advancesApi.get(id),
  });
  const refresh = () =>
    ['advances', 'invoices', 'customers', 'projects'].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );
  const undo = async (adjId) => {
    try {
      await adjustmentsApi.remove(adjId);
      toast.success('Adjustment removed');
      refresh();
    } catch (e) {
      toast.error(getErrorMessage(e));
    }
  };

  if (isLoading || !a) return <div className="card h-64 animate-pulse" />;
  const open = Number(a.balance) > 0;

  return (
    <>
      <BackLink to="/advances">All advances</BackLink>
      <PageHeader
        title={a.receipt_number}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <Link to={`/customers/${a.customer}`} className="hover:underline">
              {a.customer_name}
            </Link>{' '}
            · {formatDate(a.date)}{' '}
            <Badge color={ADVANCE_STATUS[a.status]}>{a.status_display}</Badge>
          </span>
        }
        actions={
          <>
            {open && (
              <button className="btn-primary" onClick={() => setModal('adjust')}>
                <Link2 size={16} /> Adjust to invoice
              </button>
            )}
            {open && (
              <button className="btn-secondary" onClick={() => setModal('refund')}>
                <Undo2 size={16} /> Refund
              </button>
            )}
            <DocumentButtons base={`/advances/${a.id}/`} />
            {hasRole('ADMIN') &&
              Number(a.adjusted_amount) === 0 &&
              Number(a.refunded_amount) === 0 && (
                <button className="btn-ghost text-red-600" onClick={() => setModal('cancel')}>
                  <Ban size={16} /> Cancel
                </button>
              )}
          </>
        }
      />
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <StatCard label="Received" value={formatINR(a.amount)} hint={a.mode_display} />
        <StatCard label="Adjusted" value={formatINR(a.adjusted_amount)} />
        <StatCard label="Refunded" value={formatINR(a.refunded_amount)} />
        <StatCard
          label="Unused balance"
          value={<span className={open ? 'text-green-700' : ''}>{formatINR(a.balance)}</span>}
        />
      </div>
      <div className="card mb-4">
        <InfoGrid
          items={[
            ['Project', a.project_code],
            ['Quotation', a.quotation_number],
            ['Reference', a.reference_number],
            ['Cheque', a.cheque_number && `${a.cheque_number} · ${a.bank_name}`],
            ['Received by', a.received_by_name],
            ['Notes', a.notes],
          ]}
        />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <h2 className="mb-2 font-semibold">Adjusted against invoices</h2>
          {a.adjustments.length === 0 ? (
            <p className="text-sm text-slate-500">
              Not used yet. New invoices for this customer use it automatically.
            </p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
              {a.adjustments.map((x) => (
                <li key={x.id} className="flex items-center justify-between py-2">
                  <span>
                    <Link to={`/invoices/${x.invoice}`} className="text-brand-700 hover:underline">
                      {x.invoice_number}
                    </Link>{' '}
                    · {formatDate(x.date)}
                  </span>
                  <span className="flex items-center gap-2 font-medium">
                    {formatINR(x.amount)}
                    {hasRole('ADMIN') && (
                      <button
                        className="btn-ghost px-1 text-xs text-red-600"
                        onClick={() => undo(x.id)}
                        title="Remove adjustment"
                      >
                        Undo
                      </button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="card">
          <h2 className="mb-2 font-semibold">Refunds</h2>
          {a.refunds.length === 0 ? (
            <p className="text-sm text-slate-500">No refunds.</p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
              {a.refunds.map((r) => (
                <li key={r.id} className="flex items-center justify-between py-2">
                  <span>
                    {r.refund_number} · {formatDate(r.date)} · {r.reason}
                  </span>
                  <span className="flex items-center gap-2 font-medium">
                    {formatINR(r.amount)}
                    <button
                      className="btn-ghost px-1 text-xs"
                      onClick={() => openPdf(`/advances/${a.id}/refunds/${r.id}/pdf/`)}
                    >
                      PDF
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {modal === 'adjust' && (
        <AdjustModal advance={a} open onClose={() => setModal(null)} onDone={refresh} />
      )}
      {modal === 'refund' && (
        <RefundModal advance={a} open onClose={() => setModal(null)} onDone={refresh} />
      )}
      <ReasonModal
        open={modal === 'cancel'}
        onClose={() => setModal(null)}
        title={`Cancel advance ${a.receipt_number}?`}
        description="Use this only for a wrong entry. The customer's ledger gets a reversal entry."
        confirmText="Cancel advance"
        onConfirm={async (reason) => {
          await advancesApi.action(a.id, 'cancel', { reason });
          toast.success('Advance cancelled');
          refresh();
          navigate('/advances');
        }}
      />
    </>
  );
}
