import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { advancesApi, projectsApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useLookups } from '@/hooks/useLookups';
import Modal from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import CustomerPicker from '@/components/CustomerPicker';
import { todayISO } from '@/utils/format';

export default function AdvanceModal({ open, onClose, onSaved, customerId, projectId }) {
  const qc = useQueryClient();
  const { payment_modes } = useLookups();
  const [f, setF] = useState({});
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'of', String(f.customer)],
    queryFn: () =>
      projectsApi.list({ customer: f.customer, page_size: 100 }).then((d) => d.results),
    enabled: open && !!f.customer,
  });
  useEffect(() => {
    if (open) {
      setF({
        customer: customerId || '',
        project: projectId || '',
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
    }
  }, [open, customerId, projectId]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    const errs = {};
    if (!f.customer) errs.customer = 'Select the customer';
    if (!(Number(f.amount) > 0)) errs.amount = 'Enter the amount';
    if (f.mode === 'CHEQUE' && !f.cheque_number) errs.cheque_number = 'Enter the cheque number';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true);
    try {
      const a = await advancesApi.create({
        ...f,
        project: f.project || null,
        cheque_date: f.cheque_date || null,
      });
      toast.success(`Advance receipt ${a.receipt_number} saved`);
      ['advances', 'customers', 'projects'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      onSaved?.(a);
      onClose();
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Record advance"
      size="md"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving && <Spinner />} Save advance
          </button>
        </>
      }
    >
      <div className="space-y-3">
        {!customerId && (
          <Field label="Customer" required error={errors.customer}>
            <CustomerPicker
              value={f.customer}
              onChange={(c) => setF({ ...f, customer: c.id, project: '' })}
              invalid={!!errors.customer}
            />
          </Field>
        )}
        <Field
          label="Project (optional)"
          hint="Advances for a project are used first on that project's invoices"
        >
          <Select
            value={f.project}
            onChange={set('project')}
            placeholder="Not for a specific project"
            options={projects.map((p) => ({ value: p.id, label: `${p.code} · ${p.name}` }))}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Amount (₹)" required error={errors.amount}>
            <Input
              type="number"
              step="0.01"
              inputMode="decimal"
              value={f.amount}
              onChange={set('amount')}
              autoFocus
            />
          </Field>
          <Field label="Date" required>
            <Input type="date" value={f.date} onChange={set('date')} />
          </Field>
        </div>
        <Field label="Mode">
          <Select value={f.mode} onChange={set('mode')} options={payment_modes} />
        </Field>
        {f.mode === 'CHEQUE' ? (
          <div className="grid grid-cols-3 gap-3">
            <Field label="Cheque no." required error={errors.cheque_number}>
              <Input value={f.cheque_number} onChange={set('cheque_number')} />
            </Field>
            <Field label="Cheque date">
              <Input type="date" value={f.cheque_date} onChange={set('cheque_date')} />
            </Field>
            <Field label="Bank">
              <Input value={f.bank_name} onChange={set('bank_name')} />
            </Field>
          </div>
        ) : (
          f.mode !== 'CASH' && (
            <Field label="UPI / transaction reference">
              <Input value={f.reference_number} onChange={set('reference_number')} />
            </Field>
          )
        )}
        <Field label="Notes">
          <Textarea rows={2} value={f.notes} onChange={set('notes')} />
        </Field>
      </div>
    </Modal>
  );
}
