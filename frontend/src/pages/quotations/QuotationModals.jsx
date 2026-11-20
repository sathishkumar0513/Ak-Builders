import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Plus, Trash2 } from 'lucide-react';
import { quotationsApi, usersApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import Modal from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import { formatINR, todayISO } from '@/utils/format';

function useAction(fn, onDone) {
  const [busy, setBusy] = useState(false);
  const run = async (...args) => {
    setBusy(true);
    try {
      const r = await fn(...args);
      onDone?.(r);
      return r;
    } catch (e) {
      toast.error(getErrorMessage(e));
      return null;
    } finally {
      setBusy(false);
    }
  };
  return [run, busy];
}

export function RejectModal({ quotation, open, onClose, onDone }) {
  const [reason, setReason] = useState('');
  const [run, busy] = useAction(
    (r) => quotationsApi.action(quotation.id, 'reject', { reason: r }),
    (q) => {
      toast.success('Marked as rejected');
      onDone(q);
      onClose();
    },
  );
  useEffect(() => {
    if (open) setReason('');
  }, [open]);
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title="Customer rejected the quotation"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-danger" onClick={() => run(reason)} disabled={busy}>
            {busy && <Spinner />} Mark rejected
          </button>
        </>
      }
    >
      <Field
        label="Reason (optional)"
        hint="Helps later — e.g. price too high, went with another contractor"
      >
        <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
      </Field>
      <p className="mt-2 text-xs text-slate-500">
        You can still create a revised quotation afterwards.
      </p>
    </Modal>
  );
}

export function EmailModal({ quotation, open, onClose, onDone }) {
  const [form, setForm] = useState({ to: '', cc: '', subject: '', message: '' });
  const [run, busy] = useAction(
    () =>
      quotationsApi.action(quotation.id, 'email', {
        to: form.to.split(/[,;\s]+/).filter(Boolean),
        cc: form.cc.split(/[,;\s]+/).filter(Boolean),
        subject: form.subject,
        message: form.message,
      }),
    (q) => {
      toast.success('Email sent with the PDF attached');
      onDone(q);
      onClose();
    },
  );
  useEffect(() => {
    if (!open) return;
    quotationsApi.detail(quotation.id, 'share-text').then((s) =>
      setForm({
        to: s.email || '',
        cc: '',
        subject: `Quotation ${quotation.number} (Rev ${quotation.revision})`,
        message: s.message,
      }),
    );
  }, [open, quotation]);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Email quotation"
      size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={() => run()} disabled={busy || !form.to}>
            {busy && <Spinner />} Send email
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="To" hint="Separate several addresses with commas">
          <Input
            type="email"
            value={form.to}
            onChange={set('to')}
            placeholder="customer@example.com"
          />
        </Field>
        <Field label="CC">
          <Input value={form.cc} onChange={set('cc')} />
        </Field>
        <Field label="Subject">
          <Input value={form.subject} onChange={set('subject')} />
        </Field>
        <Field label="Message">
          <Textarea rows={8} value={form.message} onChange={set('message')} />
        </Field>
        <p className="text-xs text-slate-500">
          The quotation PDF is attached automatically. A draft is marked as Sent.
        </p>
      </div>
    </Modal>
  );
}

const DEFAULT_STAGES = [
  { name: 'Advance (on work order)', percentage: '30' },
  { name: 'Mid-work', percentage: '40' },
  { name: 'Completion & handover', percentage: '30' },
];

export function ConvertModal({ quotation, open, onClose, onDone }) {
  const { data: engineers = [] } = useQuery({
    queryKey: ['users', 'engineers'],
    queryFn: () => usersApi.lookup({ role: 'SITE_ENGINEER' }),
    enabled: open,
  });
  const [form, setForm] = useState({});
  const [stages, setStages] = useState(DEFAULT_STAGES);
  useEffect(() => {
    if (open) {
      setForm({
        name: quotation.title || '',
        project_type: 'RENOVATION',
        start_date: todayISO(),
        expected_end_date: '',
        assigned_engineer: '',
      });
      setStages(DEFAULT_STAGES);
    }
  }, [open, quotation]);
  const total = stages.reduce((s, x) => s + Number(x.percentage || 0), 0);
  const amount = (pct) => (Number(quotation.grand_total) * Number(pct || 0)) / 100;
  const [run, busy] = useAction(
    () =>
      quotationsApi.action(quotation.id, 'convert', {
        ...form,
        assigned_engineer: form.assigned_engineer || null,
        expected_end_date: form.expected_end_date || null,
        stages,
      }),
    (r) => {
      toast.success(`Project ${r.project.code} created`);
      onDone(r);
      onClose();
    },
  );
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setStage = (i, k, v) => setStages(stages.map((s, n) => (n === i ? { ...s, [k]: v } : s)));

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Convert to project"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={() => run()}
            disabled={busy || Math.abs(total - 100) > 0.001}
          >
            {busy && <Spinner />} Create project
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Contract value <b>{formatINR(quotation.grand_total)}</b> for{' '}
          {quotation.customer_detail.name}. The quotation will be marked <b>Converted</b>.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Project name" className="sm:col-span-2">
            <Input
              value={form.name || ''}
              onChange={set('name')}
              placeholder={`${quotation.customer_detail.name} – ${quotation.number}`}
            />
          </Field>
          <Field label="Type">
            <Select
              value={form.project_type}
              onChange={set('project_type')}
              options={[
                { value: 'RENOVATION', label: 'Renovation' },
                { value: 'NEW', label: 'New construction' },
                { value: 'SUPPLY', label: 'Material supply only' },
              ]}
            />
          </Field>
          <Field label="Site engineer">
            <Select
              value={form.assigned_engineer}
              onChange={set('assigned_engineer')}
              placeholder="Assign later"
              options={engineers.map((u) => ({ value: u.id, label: u.name }))}
            />
          </Field>
          <Field label="Start date">
            <Input type="date" value={form.start_date || ''} onChange={set('start_date')} />
          </Field>
          <Field label="Expected completion">
            <Input
              type="date"
              value={form.expected_end_date || ''}
              onChange={set('expected_end_date')}
            />
          </Field>
        </div>
        <div>
          <p className="label">Payment stages</p>
          <div className="space-y-2">
            {stages.map((s, i) => (
              <div key={i} className="grid grid-cols-[1fr_80px_110px_32px] items-center gap-2">
                <Input
                  value={s.name}
                  onChange={(e) => setStage(i, 'name', e.target.value)}
                  aria-label={`Stage ${i + 1} name`}
                />
                <div className="relative">
                  <Input
                    type="number"
                    step="0.01"
                    className="pr-6 text-right"
                    value={s.percentage}
                    onChange={(e) => setStage(i, 'percentage', e.target.value)}
                    aria-label={`Stage ${i + 1} percent`}
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400">
                    %
                  </span>
                </div>
                <span className="text-right text-sm tabular-nums">
                  {formatINR(amount(s.percentage))}
                </span>
                <button
                  type="button"
                  className="btn-ghost text-red-600"
                  disabled={stages.length === 1}
                  onClick={() => setStages(stages.filter((_, n) => n !== i))}
                  aria-label={`Remove stage ${i + 1}`}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
          <div className="mt-2 flex items-center justify-between">
            <button
              type="button"
              className="btn-ghost text-sm"
              onClick={() =>
                setStages([...stages, { name: '', percentage: String(Math.max(0, 100 - total)) }])
              }
            >
              <Plus size={14} /> Add stage
            </button>
            <span
              className={`text-sm font-medium ${Math.abs(total - 100) > 0.001 ? 'text-red-600' : 'text-green-700'}`}
            >
              Total {total.toFixed(2)}%{Math.abs(total - 100) > 0.001 && ' — must be 100%'}
            </span>
          </div>
        </div>
      </div>
    </Modal>
  );
}
