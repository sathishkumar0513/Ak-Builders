import { useEffect } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import toast from 'react-hot-toast';
import { materialsApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import Modal from '@/components/ui/Modal';
import { Field, Input } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import { formatQty, todayISO } from '@/utils/format';

const schema = z.object({
  direction: z.enum(['IN', 'OUT']),
  quantity: z.coerce.number().positive('Enter a quantity'),
  reason: z.string().trim().min(3, 'Explain why (e.g. damaged bags, physical count)'),
  date: z.string(),
});

export default function StockAdjustModal({ material, open, onClose, onSaved }) {
  const {
    register,
    handleSubmit,
    reset,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });
  const [dir, qty] = useWatch({ control, name: ['direction', 'quantity'] });
  useEffect(() => {
    if (open) reset({ direction: 'OUT', quantity: '', reason: '', date: todayISO() });
  }, [open, reset]);
  const current = Number(material?.stock_quantity || 0);
  const after = dir === 'IN' ? current + Number(qty || 0) : current - Number(qty || 0);

  const onSubmit = async (values) => {
    try {
      await materialsApi.action(material.id, 'adjust-stock', values);
      toast.success('Stock adjusted');
      onSaved();
      onClose();
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title="Adjust stock"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" form="adjust-form" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} Save
          </button>
        </>
      }
    >
      <form id="adjust-form" onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate>
        <div className="grid grid-cols-2 gap-2">
          {[
            ['OUT', 'Remove stock'],
            ['IN', 'Add stock'],
          ].map(([v, l]) => (
            <label
              key={v}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 p-2 text-sm has-[:checked]:border-brand-500 has-[:checked]:bg-brand-50 dark:border-slate-600 dark:has-[:checked]:bg-slate-700"
            >
              <input
                type="radio"
                value={v}
                className="accent-brand-600"
                {...register('direction')}
              />{' '}
              {l}
            </label>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label={`Quantity (${material?.unit})`} error={errors.quantity}>
            <Input type="number" step="any" autoFocus {...register('quantity')} />
          </Field>
          <Field label="Date">
            <Input type="date" {...register('date')} />
          </Field>
        </div>
        <Field label="Reason" error={errors.reason}>
          <Input placeholder="e.g. 3 bags damaged by rain" {...register('reason')} />
        </Field>
        <p
          className={`text-sm ${after < 0 ? 'text-red-600' : 'text-slate-600 dark:text-slate-300'}`}
        >
          Stock: {formatQty(current)} → <b>{formatQty(after)}</b> {material?.unit}{' '}
          {after < 0 && '(not allowed — stock cannot go below zero)'}
        </p>
      </form>
    </Modal>
  );
}
