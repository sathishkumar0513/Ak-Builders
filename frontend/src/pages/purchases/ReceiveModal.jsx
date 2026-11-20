import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { purchasesApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import Modal from '@/components/ui/Modal';
import { Field, Input } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import { formatQty, todayISO } from '@/utils/format';

export default function ReceiveModal({ purchase, open, onClose, onSaved }) {
  const pending = (purchase?.items || []).filter(
    (i) => i.material && Number(i.pending_quantity) > 0,
  );
  const [qty, setQty] = useState({});
  const [date, setDate] = useState(todayISO());
  const [updatePrice, setUpdatePrice] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setQty(Object.fromEntries(pending.map((i) => [i.id, i.pending_quantity])));
      setDate(todayISO());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const save = async () => {
    const lines = Object.entries(qty)
      .filter(([, q]) => Number(q) > 0)
      .map(([item, quantity]) => ({ item: Number(item), quantity }));
    if (!lines.length) return toast.error('Enter the quantity received for at least one item');
    setSaving(true);
    try {
      await purchasesApi.action(purchase.id, 'receive', {
        lines,
        date,
        update_purchase_price: updatePrice,
      });
      toast.success('Goods received — stock updated');
      onSaved();
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
      title="Receive goods"
      size="lg"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={save} disabled={saving}>
            {saving && <Spinner />} Add to stock
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Received on" className="max-w-xs">
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2 text-left">Item</th>
              <th className="text-right">Ordered</th>
              <th className="text-right">Pending</th>
              <th className="w-32 text-right">Receiving now</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {pending.map((i) => (
              <tr key={i.id}>
                <td className="py-2">{i.description}</td>
                <td className="text-right">
                  {formatQty(i.quantity)} {i.unit}
                </td>
                <td className="text-right">{formatQty(i.pending_quantity)}</td>
                <td className="py-1 pl-2">
                  <input
                    type="number"
                    step="any"
                    min="0"
                    max={i.pending_quantity}
                    className="input px-2 text-right"
                    value={qty[i.id] ?? ''}
                    onChange={(e) => setQty({ ...qty, [i.id]: e.target.value })}
                    aria-label={`Quantity received for ${i.description}`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="accent-brand-600"
            checked={updatePrice}
            onChange={(e) => setUpdatePrice(e.target.checked)}
          />
          Update each material&apos;s purchase price to this bill&apos;s rate (recorded in price
          history)
        </label>
      </div>
    </Modal>
  );
}
