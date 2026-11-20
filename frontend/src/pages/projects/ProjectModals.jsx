import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { Plus, Trash2 } from 'lucide-react';
import { projectsApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import Modal from '@/components/ui/Modal';
import { Field, Input, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import MaterialPicker from '@/components/lineitems/MaterialPicker';
import { useMaterialCatalog } from '@/hooks/useMaterialCatalog';
import { formatINR, formatQty, todayISO } from '@/utils/format';

export function StagesModal({ project, open, onClose, onSaved }) {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open)
      setRows(
        project.payment_stages.map((s) => ({
          id: s.id,
          name: s.name,
          percentage: String(Number(s.percentage)),
          due_date: s.due_date || '',
          locked: s.invoices.length > 0 || Number(s.amount_received) > 0,
        })),
      );
  }, [open, project]);
  const total = rows.reduce((s, r) => s + Number(r.percentage || 0), 0);
  const set = (i, k, v) => setRows(rows.map((r, n) => (n === i ? { ...r, [k]: v } : r)));
  const save = async () => {
    setBusy(true);
    try {
      await projectsApi.action(project.id, 'stages', {
        stages: rows.map(({ id, name, percentage, due_date }) => ({
          ...(id ? { id } : {}),
          name,
          percentage,
          due_date: due_date || null,
        })),
      });
      toast.success('Payment stages saved');
      onSaved();
      onClose();
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const ok = Math.abs(total - 100) < 0.001 && rows.every((r) => r.name.trim());
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Payment stages"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={save} disabled={busy || !ok}>
            {busy && <Spinner />} Save stages
          </button>
        </>
      }
    >
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
        Contract value <b>{formatINR(project.contract_value)}</b>. Stages already invoiced or paid
        are locked.
      </p>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div
            key={r.id || `n${i}`}
            className="grid grid-cols-[1fr_80px_140px_110px_32px] items-center gap-2"
          >
            <Input
              value={r.name}
              disabled={r.locked}
              onChange={(e) => set(i, 'name', e.target.value)}
              placeholder="Stage name"
              aria-label="Stage name"
            />
            <Input
              type="number"
              step="0.01"
              className="text-right"
              value={r.percentage}
              disabled={r.locked}
              onChange={(e) => set(i, 'percentage', e.target.value)}
              aria-label="Percent"
            />
            <Input
              type="date"
              value={r.due_date}
              onChange={(e) => set(i, 'due_date', e.target.value)}
              aria-label="Due date"
              title="Due date"
            />
            <span className="text-right text-sm tabular-nums">
              {formatINR((Number(project.contract_value) * Number(r.percentage || 0)) / 100)}
            </span>
            <button
              className="btn-ghost text-red-600"
              disabled={r.locked}
              onClick={() => setRows(rows.filter((_, n) => n !== i))}
              aria-label="Remove stage"
            >
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <button
          className="btn-ghost text-sm"
          onClick={() =>
            setRows([
              ...rows,
              { name: '', percentage: String(Math.max(0, 100 - total)), due_date: '' },
            ])
          }
        >
          <Plus size={14} /> Add stage
        </button>
        <span
          className={`text-sm font-medium ${Math.abs(total - 100) > 0.001 ? 'text-red-600' : 'text-green-700'}`}
        >
          Total {total.toFixed(2)}%
        </span>
      </div>
    </Modal>
  );
}

export function IssueMaterialModal({ project, open, isReturn, siteStock = [], onClose, onSaved }) {
  const { data: catalog = [] } = useMaterialCatalog();
  const [f, setF] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open)
      setF({
        material: '',
        quantity: '',
        issue_date: todayISO(),
        notes: '',
        received_by_name: '',
        vehicle_number: '',
      });
  }, [open]);
  const m = catalog.find((x) => x.id === Number(f.material));
  const atSite = siteStock.find((r) => r.material === Number(f.material))?.net;
  const limit = isReturn ? Number(atSite || 0) : Number(m?.stock_quantity || 0);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    setBusy(true);
    try {
      await projectsApi.action(project.id, 'issue-material', { ...f, is_return: !!isReturn });
      toast.success(
        isReturn ? 'Return recorded — stock updated' : 'Material issued — stock updated',
      );
      onSaved();
      onClose();
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const tooMuch = m && Number(f.quantity) > limit;
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={isReturn ? 'Return material to store' : 'Issue material to site'}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={save}
            disabled={busy || !f.material || !(Number(f.quantity) > 0) || tooMuch}
          >
            {busy && <Spinner />} {isReturn ? 'Record return' : 'Issue'}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Material">
          {isReturn ? (
            <select className="input" value={f.material} onChange={set('material')}>
              <option value="">Select material at this site</option>
              {siteStock
                .filter((r) => Number(r.net) > 0)
                .map((r) => (
                  <option key={r.material} value={r.material}>
                    {r.name} · {formatQty(r.net)} {r.unit} at site
                  </option>
                ))}
            </select>
          ) : (
            <MaterialPicker value={f.material} onSelect={(x) => setF({ ...f, material: x.id })} />
          )}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field
            label={`Quantity${m ? ` (${m.unit})` : ''}`}
            error={
              tooMuch
                ? `Only ${formatQty(limit)} ${m.unit} ${isReturn ? 'at site' : 'in stock'}`
                : undefined
            }
            hint={
              m && !tooMuch
                ? `${isReturn ? 'At site' : 'In stock'}: ${formatQty(limit)} ${m.unit}`
                : undefined
            }
          >
            <Input
              type="number"
              step="any"
              inputMode="decimal"
              value={f.quantity}
              onChange={set('quantity')}
            />
          </Field>
          <Field label="Date">
            <Input type="date" value={f.issue_date} onChange={set('issue_date')} />
          </Field>
        </div>
        {!isReturn && (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Received at site by">
              <Input value={f.received_by_name} onChange={set('received_by_name')} />
            </Field>
            <Field label="Vehicle no.">
              <Input
                value={f.vehicle_number}
                onChange={set('vehicle_number')}
                placeholder="TN 69 AB 1234"
              />
            </Field>
          </div>
        )}
        <Field label="Notes">
          <Input
            value={f.notes}
            onChange={set('notes')}
            placeholder={isReturn ? 'e.g. Excess after slab' : 'e.g. For first floor columns'}
          />
        </Field>
      </div>
    </Modal>
  );
}

export function ProgressForm({ project, onSaved }) {
  const [f, setF] = useState({
    note: '',
    date: todayISO(),
    progress_percent: '',
    workers_on_site: '',
  });
  const [photos, setPhotos] = useState([]);
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!f.note.trim()) return toast.error('Write what was done today');
    const fd = new FormData();
    Object.entries(f).forEach(([k, v]) => v !== '' && fd.append(k, v));
    photos.forEach((p) => fd.append('photos', p));
    setBusy(true);
    try {
      await projectsApi.action(project.id, 'add-progress', fd);
      toast.success('Progress saved');
      setF({ note: '', date: todayISO(), progress_percent: '', workers_on_site: '' });
      setPhotos([]);
      onSaved();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="card space-y-3">
      <h2 className="font-semibold">Add today&apos;s update</h2>
      <Textarea
        rows={3}
        value={f.note}
        onChange={(e) => setF({ ...f, note: e.target.value })}
        placeholder="What was done today, issues, material needed…"
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Date">
          <Input
            type="date"
            value={f.date}
            onChange={(e) => setF({ ...f, date: e.target.value })}
          />
        </Field>
        <Field label="Overall progress %">
          <Input
            type="number"
            min="0"
            max="100"
            value={f.progress_percent}
            onChange={(e) => setF({ ...f, progress_percent: e.target.value })}
            placeholder={String(Number(project.progress_percent))}
          />
        </Field>
        <Field label="Workers on site">
          <Input
            type="number"
            min="0"
            value={f.workers_on_site}
            onChange={(e) => setF({ ...f, workers_on_site: e.target.value })}
          />
        </Field>
        <Field label="Photos (max 10)">
          <label className="btn-secondary w-full cursor-pointer">
            {photos.length ? `${photos.length} selected` : 'Take / choose'}
            <input
              type="file"
              accept="image/*"
              multiple
              capture="environment"
              className="hidden"
              onChange={(e) => setPhotos(Array.from(e.target.files || []).slice(0, 10))}
            />
          </label>
        </Field>
      </div>
      {photos.length > 0 && (
        <div className="flex gap-2 overflow-x-auto">
          {photos.map((p, i) => (
            <img
              key={i}
              src={URL.createObjectURL(p)}
              alt=""
              className="h-16 w-16 shrink-0 rounded object-cover"
            />
          ))}
        </div>
      )}
      <div className="flex justify-end">
        <button className="btn-primary" disabled={busy}>
          {busy && <Spinner />} Save update
        </button>
      </div>
    </form>
  );
}
