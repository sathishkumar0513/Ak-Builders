import { useEffect } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import toast from 'react-hot-toast';
import { supplierPaymentsApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import { useLookups } from '@/hooks/useLookups';
import Modal from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import { formatINR, todayISO } from '@/utils/format';

/**
 * Pay a supplier. Pass `purchase` to pay against one bill (limit = its balance),
 * or only `supplier` for an on-account payment (limit = total payable).
 */
export default function SupplierPaymentModal({
  open,
  supplier,
  purchase,
  purchases = [],
  maxAmount,
  onClose,
  onSaved,
}) {
  const { payment_modes } = useLookups();
  const schema = z.object({
    purchase: z.string(),
    amount: z.coerce.number().positive('Enter the amount'),
    date: z.string().min(1),
    mode: z.string().min(1),
    reference_number: z.string().trim(),
    notes: z.string().trim(),
  });
  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });
  const selectedPurchaseId = useWatch({ control, name: 'purchase' });
  const selected = purchase || purchases.find((p) => String(p.id) === String(selectedPurchaseId));
  const limit = selected ? Number(selected.balance_due) : Number(maxAmount ?? 0);
  const mode = useWatch({ control, name: 'mode' });

  useEffect(() => {
    if (open)
      reset({
        purchase: purchase ? String(purchase.id) : '',
        amount: purchase ? purchase.balance_due : '',
        date: todayISO(),
        mode: 'BANK',
        reference_number: '',
        notes: '',
      });
  }, [open, purchase, reset]);

  const onSubmit = async (values) => {
    if (values.amount > limit) {
      setError('amount', { message: `Cannot be more than ${formatINR(limit)}` });
      return;
    }
    try {
      await supplierPaymentsApi.create({
        ...values,
        supplier: supplier.id,
        purchase: values.purchase || null,
      });
      toast.success('Payment recorded');
      onSaved?.();
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
      title={`Pay ${supplier?.name || ''}`}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" form="sp-form" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} Save payment
          </button>
        </>
      }
    >
      <form id="sp-form" onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate>
        {!purchase && (
          <Field label="Against bill" hint="Leave as 'On account' to reduce the overall balance">
            <Select
              placeholder="On account (no specific bill)"
              {...register('purchase')}
              options={purchases
                .filter((p) => Number(p.balance_due) > 0)
                .map((p) => ({
                  value: String(p.id),
                  label: `${p.po_number} · due ${formatINR(p.balance_due)}`,
                }))}
              onChange={(e) => {
                setValue('purchase', e.target.value);
                const p = purchases.find((x) => String(x.id) === e.target.value);
                if (p) setValue('amount', p.balance_due);
              }}
            />
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Amount (₹)" error={errors.amount} hint={`Max ${formatINR(limit)}`}>
            <Input type="number" step="0.01" inputMode="decimal" {...register('amount')} />
          </Field>
          <Field label="Date">
            <Input type="date" {...register('date')} />
          </Field>
        </div>
        <Field label="Mode">
          <Select options={payment_modes} {...register('mode')} />
        </Field>
        <Field label={mode === 'CHEQUE' ? 'Cheque number' : 'Reference / UTR'}>
          <Input {...register('reference_number')} />
        </Field>
        <Field label="Notes">
          <Textarea rows={2} {...register('notes')} />
        </Field>
      </form>
    </Modal>
  );
}
