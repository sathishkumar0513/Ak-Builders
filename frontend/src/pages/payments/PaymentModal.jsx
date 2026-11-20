import { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { customersApi, paymentsApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useLookups } from '@/hooks/useLookups';
import Modal from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import CustomerPicker from '@/components/CustomerPicker';
import { formatDate, formatINR, todayISO } from '@/utils/format';

/**
 * Record a customer payment against an unpaid invoice or an un-invoiced project stage.
 * Preselect with customerId + invoiceId / stageId. onSaved(payment).
 */
export default function PaymentModal({ open, onClose, onSaved, customerId, invoiceId, stageId }) {
  const qc = useQueryClient();
  const { payment_modes } = useLookups();
  const [customer, setCustomer] = useState(customerId || '');
  const [target, setTarget] = useState('');
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const { data: items, isFetching } = useQuery({
    queryKey: ['customers', String(customer), 'open-items'],
    queryFn: () => customersApi.detail(customer, 'open-items'),
    enabled: open && !!customer,
  });
  const options = useMemo(
    () => [
      ...(items?.invoices || []).map((i) => ({
        value: `inv:${i.id}`,
        label: `Invoice ${i.number} · ${formatDate(i.date)} · due ${formatINR(i.balance_due)}`,
        max: i.balance_due,
      })),
      ...(items?.stages || []).map((s) => ({
        value: `stg:${s.id}`,
        label: `${s.project_code} · ${s.name} (not invoiced) · left ${formatINR(s.balance)}`,
        max: s.balance,
      })),
    ],
    [items],
  );
  const selected = options.find((o) => o.value === target);

  useEffect(() => {
    if (!open) return;
    setCustomer(customerId || '');
    setTarget(invoiceId ? `inv:${invoiceId}` : stageId ? `stg:${stageId}` : '');
    setForm({
      amount: '',
      date: todayISO(),
      mode: 'UPI',
      reference_number: '',
      cheque_number: '',
      cheque_date: '',
      bank_name: '',
      notes: '',
    });
    setErrors({});
  }, [open, customerId, invoiceId, stageId]);
  useEffect(() => {
    if (selected && !form.amount) setForm((f) => ({ ...f, amount: selected.max }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.value]);
  useEffect(() => {
    if (open && items && !target && options.length === 1) setTarget(options[0].value);
  }, [open, items, target, options]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const save = async () => {
    const errs = {};
    if (!customer) errs.customer = 'Select the customer';
    if (!target) errs.target = 'Choose what this payment is for';
    if (!(Number(form.amount) > 0)) errs.amount = 'Enter the amount';
    else if (selected && Number(form.amount) > Number(selected.max))
      errs.amount = `Cannot be more than ${formatINR(selected.max)}`;
    if (form.mode === 'CHEQUE' && !form.cheque_number)
      errs.cheque_number = 'Enter the cheque number';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const [kind, id] = target.split(':');
    setSaving(true);
    try {
      const p = await paymentsApi.create({
        ...form,
        customer,
        cheque_date: form.cheque_date || null,
        invoice: kind === 'inv' ? Number(id) : null,
        payment_stage: kind === 'stg' ? Number(id) : null,
      });
      toast.success(`Receipt ${p.receipt_number} saved`);
      ['invoices', 'payments', 'projects', 'customers', 'advances'].forEach((k) =>
        qc.invalidateQueries({ queryKey: [k] }),
      );
      onSaved?.(p);
      onClose();
    } catch (e) {
      const fe = e?.response?.data?.errors;
      if (fe && Object.keys(fe).length)
        setErrors(
          Object.fromEntries(
            Object.entries(fe).map(([k, v]) => [
              k === 'invoice' || k === 'payment_stage' ? 'target' : k,
              [].concat(v)[0],
            ]),
          ),
        );
      toast.error(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Record payment"
      size="md"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving && <Spinner />} Save receipt
          </button>
        </>
      }
    >
      <div className="space-y-3">
        {!customerId && (
          <Field label="Customer" required error={errors.customer}>
            <CustomerPicker
              value={customer}
              onChange={(c) => {
                setCustomer(c.id);
                setTarget('');
              }}
              invalid={!!errors.customer}
            />
          </Field>
        )}
        {customer && (
          <Field
            label="Payment for"
            required
            error={errors.target}
            hint={
              !isFetching && options.length === 0
                ? 'Nothing is due. Money received before billing should be recorded as an Advance.'
                : undefined
            }
          >
            <Select
              value={target}
              onChange={(e) => {
                setTarget(e.target.value);
                setForm((f) => ({ ...f, amount: '' }));
              }}
              placeholder={isFetching ? 'Loading…' : 'Select invoice or project stage'}
              options={options}
            />
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field
            label="Amount (₹)"
            required
            error={errors.amount}
            hint={selected ? `Due ${formatINR(selected.max)}` : undefined}
          >
            <Input
              type="number"
              step="0.01"
              inputMode="decimal"
              value={form.amount ?? ''}
              onChange={set('amount')}
            />
          </Field>
          <Field label="Date" required>
            <Input type="date" value={form.date || ''} onChange={set('date')} />
          </Field>
        </div>
        <Field label="Mode">
          <Select value={form.mode} onChange={set('mode')} options={payment_modes} />
        </Field>
        {form.mode === 'CHEQUE' ? (
          <div className="grid grid-cols-3 gap-3">
            <Field label="Cheque no." required error={errors.cheque_number}>
              <Input value={form.cheque_number} onChange={set('cheque_number')} />
            </Field>
            <Field label="Cheque date">
              <Input type="date" value={form.cheque_date} onChange={set('cheque_date')} />
            </Field>
            <Field label="Bank">
              <Input value={form.bank_name} onChange={set('bank_name')} />
            </Field>
          </div>
        ) : (
          form.mode !== 'CASH' && (
            <Field label="UPI / transaction reference">
              <Input
                value={form.reference_number}
                onChange={set('reference_number')}
                placeholder="e.g. UTR number"
              />
            </Field>
          )
        )}
        <Field label="Notes">
          <Textarea rows={2} value={form.notes} onChange={set('notes')} />
        </Field>
      </div>
    </Modal>
  );
}
