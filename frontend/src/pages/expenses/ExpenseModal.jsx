import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Paperclip } from 'lucide-react';
import { expensesApi, projectsApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { useLookups } from '@/hooks/useLookups';
import Modal from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import { EXPENSE_CATEGORIES } from '@/utils/constants';
import { todayISO } from '@/utils/format';

const MAX_BILL = 8 * 1024 * 1024;

/** Add or edit an expense. `projectId` locks the project (used on the project page). */
export default function ExpenseModal({ open, onClose, expense, projectId }) {
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const engineer = !hasRole('ADMIN', 'ACCOUNTANT');
  const { payment_modes } = useLookups();
  const [f, setF] = useState({});
  const [bill, setBill] = useState(null);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'for-expense'],
    queryFn: () =>
      projectsApi
        .list({ page_size: 200 })
        .then((d) => d.results.filter((p) => p.status !== 'CANCELLED')),
    enabled: open && !projectId,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!open) return;
    setF(
      expense
        ? {
            project: expense.project || '',
            category: expense.category,
            date: expense.date,
            amount: expense.amount,
            paid_to: expense.paid_to,
            mode: expense.mode,
            reference_number: expense.reference_number,
            description: expense.description,
            workers_count: expense.workers_count ?? '',
            work_days: expense.work_days ?? '',
          }
        : {
            project: projectId || '',
            category: 'LABOUR',
            date: todayISO(),
            amount: '',
            paid_to: '',
            mode: 'CASH',
            reference_number: '',
            description: '',
            workers_count: '',
            work_days: '',
          },
    );
    setBill(null);
    setErrors({});
  }, [open, expense, projectId]);

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const labour = f.category === 'LABOUR';

  // labour: workers × days × daily wage helper
  const [wage, setWage] = useState('');
  useEffect(() => setWage(''), [open]);
  const applyWage = (w) => {
    setWage(w);
    const total = Number(f.workers_count) * Number(f.work_days || 1) * Number(w);
    if (total > 0) setF((cur) => ({ ...cur, amount: total.toFixed(2) }));
  };

  const save = async () => {
    const errs = {};
    if (!(Number(f.amount) > 0)) errs.amount = 'Enter the amount';
    if (!f.date) errs.date = 'Enter the date';
    else if (f.date > todayISO()) errs.date = "Can't be a future date";
    if (engineer && !f.project && !projectId) errs.project = 'Choose your project';
    if (bill && bill.size > MAX_BILL) errs.bill = 'Bill file must be under 8 MB';
    setErrors(errs);
    if (Object.keys(errs).length) return;

    const payload = {
      ...f,
      project: f.project || projectId || null,
      workers_count: labour && f.workers_count !== '' ? f.workers_count : null,
      work_days: labour && f.work_days !== '' ? f.work_days : null,
    };
    let body = payload;
    if (bill) {
      body = new FormData();
      Object.entries(payload).forEach(([k, v]) => body.append(k, v === null ? '' : v));
      body.append('bill_attachment', bill);
    }
    setSaving(true);
    try {
      const saved = expense
        ? await expensesApi.update(expense.id, body)
        : await expensesApi.create(body);
      toast.success(
        expense
          ? 'Expense updated'
          : `Expense ${saved.voucher_number} saved${saved.is_approved ? '' : ' — waiting for approval'}`,
      );
      ['expenses', 'projects', 'dashboard'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      onClose();
    } catch (e) {
      const data = e?.response?.data;
      if (data?.errors) {
        setErrors(Object.fromEntries(Object.entries(data.errors).map(([k, v]) => [k, v[0]])));
      }
      toast.error(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={expense ? `Edit ${expense.voucher_number}` : 'Add expense'}
      size="md"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving && <Spinner />} Save expense
          </button>
        </>
      }
    >
      <div className="space-y-3">
        {!projectId && (
          <Field
            label="Project"
            required={engineer}
            error={errors.project}
            hint={engineer ? undefined : 'Leave empty for office / overhead expenses'}
          >
            <Select
              value={f.project}
              onChange={set('project')}
              placeholder={engineer ? 'Choose project' : 'Office / overhead (no project)'}
              options={projects.map((p) => ({ value: p.id, label: `${p.code} · ${p.name}` }))}
              invalid={!!errors.project}
            />
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Category" required>
            <Select value={f.category} onChange={set('category')} options={EXPENSE_CATEGORIES} />
          </Field>
          <Field label="Date" required error={errors.date}>
            <Input
              type="date"
              max={todayISO()}
              value={f.date}
              onChange={set('date')}
              invalid={!!errors.date}
            />
          </Field>
        </div>
        {labour && (
          <div className="grid grid-cols-3 gap-3 rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
            <Field label="Workers" error={errors.workers_count}>
              <Input
                type="number"
                min="1"
                inputMode="numeric"
                value={f.workers_count}
                onChange={set('workers_count')}
              />
            </Field>
            <Field label="Days">
              <Input
                type="number"
                step="0.5"
                min="0.5"
                inputMode="decimal"
                value={f.work_days}
                onChange={set('work_days')}
              />
            </Field>
            <Field label="Wage / day (₹)" hint="Fills the amount">
              <Input
                type="number"
                inputMode="decimal"
                value={wage}
                onChange={(e) => applyWage(e.target.value)}
                disabled={!f.workers_count}
              />
            </Field>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Amount (₹)" required error={errors.amount}>
            <Input
              type="number"
              step="0.01"
              inputMode="decimal"
              value={f.amount}
              onChange={set('amount')}
              invalid={!!errors.amount}
            />
          </Field>
          <Field label="Paid by">
            <Select value={f.mode} onChange={set('mode')} options={payment_modes} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label={labour ? 'Paid to (mestri / team)' : 'Paid to'}>
            <Input value={f.paid_to} onChange={set('paid_to')} />
          </Field>
          <Field label="Reference / bill no.">
            <Input value={f.reference_number} onChange={set('reference_number')} />
          </Field>
        </div>
        <Field label="Description">
          <Textarea rows={2} value={f.description} onChange={set('description')} />
        </Field>
        <Field label="Bill photo or PDF" error={errors.bill || errors.bill_attachment}>
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800">
            <Paperclip size={16} />
            <span className="truncate">
              {bill?.name ||
                (expense?.bill_attachment ? 'Replace attached bill' : 'Attach bill (optional)')}
            </span>
            <input
              type="file"
              accept="image/*,application/pdf"
              className="hidden"
              onChange={(e) => setBill(e.target.files?.[0] || null)}
            />
          </label>
        </Field>
      </div>
    </Modal>
  );
}
