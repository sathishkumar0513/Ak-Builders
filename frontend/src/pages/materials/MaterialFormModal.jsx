import { useEffect } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { categoriesApi, materialsApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import { useLookups } from '@/hooks/useLookups';
import Modal from '@/components/ui/Modal';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import { GST_RATES } from '@/components/lineitems/lineDefaults';

const money = z.coerce
  .number({ invalid_type_error: 'Enter an amount' })
  .min(0, 'Cannot be negative');
const schema = z.object({
  category: z.coerce.number().min(1, 'Select a category'),
  name: z.string().trim().min(2, 'Enter the material name'),
  brand: z.string().trim(),
  sku: z.string().trim(),
  hsn_code: z
    .string()
    .trim()
    .refine((v) => v === '' || /^(\d{4}|\d{6}|\d{8})$/.test(v), '4, 6 or 8 digits'),
  unit: z.string().min(1, 'Select a unit'),
  purchase_price: money,
  selling_price: money,
  gst_rate: z.string(),
  reorder_level: z.coerce.number().min(0),
  opening_stock: z.coerce.number().min(0).optional(),
  is_active: z.boolean(),
  description: z.string().trim(),
  price_change_reason: z.string().trim().optional(),
  allow_below_cost: z.boolean().optional(),
});

export default function MaterialFormModal({ material, onClose, onSaved }) {
  const { units } = useLookups();
  const { data: categories = [] } = useQuery({
    queryKey: ['material-categories'],
    queryFn: () => categoriesApi.list(),
  });
  const isEdit = !!material?.id;
  const {
    register,
    handleSubmit,
    reset,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });
  const [pp, sp] = useWatch({ control, name: ['purchase_price', 'selling_price'] });
  const priceChanged =
    isEdit &&
    (Number(pp) !== Number(material.purchase_price) ||
      Number(sp) !== Number(material.selling_price));
  const belowCost = Number(sp) < Number(pp);
  const margin =
    Number(pp) > 0 ? (((Number(sp) - Number(pp)) / Number(pp)) * 100).toFixed(1) : null;

  useEffect(() => {
    if (!material) return;
    reset(
      isEdit
        ? {
            ...material,
            gst_rate: String(Number(material.gst_rate)),
            category: material.category,
            price_change_reason: '',
            allow_below_cost: false,
          }
        : {
            category: '',
            name: '',
            brand: '',
            sku: '',
            hsn_code: '',
            unit: 'bag',
            purchase_price: '',
            selling_price: '',
            gst_rate: '18',
            reorder_level: '0',
            opening_stock: '0',
            is_active: true,
            description: '',
            allow_below_cost: false,
          },
    );
  }, [material, isEdit, reset]);

  const onSubmit = async (values) => {
    const payload = { ...values };
    if (isEdit) delete payload.opening_stock;
    if (!priceChanged) delete payload.price_change_reason;
    try {
      const saved = isEdit
        ? await materialsApi.update(material.id, payload)
        : await materialsApi.create(payload);
      toast.success(isEdit ? 'Material updated' : 'Material added');
      onSaved?.(saved);
      onClose();
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  return (
    <Modal
      open={!!material}
      onClose={onClose}
      size="lg"
      title={isEdit ? `Edit ${material.name}` : 'Add material'}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" form="material-form" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} Save
          </button>
        </>
      }
    >
      <form
        id="material-form"
        onSubmit={handleSubmit(onSubmit)}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        noValidate
      >
        <Field label="Category" required error={errors.category}>
          <Select
            placeholder="Select"
            options={categories.map((c) => ({ value: c.id, label: c.name }))}
            {...register('category')}
          />
        </Field>
        <Field label="Material name" required error={errors.name}>
          <Input placeholder="e.g. TMT Rod 12 mm" {...register('name')} />
        </Field>
        <Field label="Brand" error={errors.brand}>
          <Input {...register('brand')} />
        </Field>
        <Field label="HSN code" error={errors.hsn_code}>
          <Input inputMode="numeric" maxLength={8} {...register('hsn_code')} />
        </Field>
        <Field label="Unit" required error={errors.unit}>
          <Select options={units} {...register('unit')} />
        </Field>
        <Field label="GST %" error={errors.gst_rate}>
          <Select
            options={GST_RATES.map((r) => ({ value: r, label: `${r}%` }))}
            {...register('gst_rate')}
          />
        </Field>
        <Field label="Purchase price (₹)" required error={errors.purchase_price}>
          <Input type="number" step="0.01" inputMode="decimal" {...register('purchase_price')} />
        </Field>
        <Field
          label="Selling price (₹)"
          required
          error={errors.selling_price}
          hint={margin !== null && !errors.selling_price ? `Margin ${margin}%` : undefined}
        >
          <Input type="number" step="0.01" inputMode="decimal" {...register('selling_price')} />
        </Field>
        <Field
          label="Reorder level"
          hint="Low-stock alert at or below this"
          error={errors.reorder_level}
        >
          <Input type="number" step="any" {...register('reorder_level')} />
        </Field>
        {!isEdit && (
          <Field
            label="Opening stock"
            hint="Current quantity in your store"
            error={errors.opening_stock}
          >
            <Input type="number" step="any" {...register('opening_stock')} />
          </Field>
        )}
        <Field label="SKU / code" error={errors.sku}>
          <Input {...register('sku')} />
        </Field>
        {belowCost && (
          <label className="flex items-center gap-2 rounded-lg bg-amber-50 p-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200 sm:col-span-2 lg:col-span-3">
            <input type="checkbox" className="accent-brand-600" {...register('allow_below_cost')} />{' '}
            Selling price is below purchase price — allow below cost
          </label>
        )}
        {priceChanged && (
          <Field
            label="Reason for price change"
            className="sm:col-span-2 lg:col-span-3"
            hint="Saved in the price history"
          >
            <Input
              placeholder="e.g. Dealer rate increased from 1 Nov"
              {...register('price_change_reason')}
            />
          </Field>
        )}
        <Field label="Description" className="sm:col-span-2 lg:col-span-3">
          <Textarea rows={2} {...register('description')} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-brand-600" {...register('is_active')} />{' '}
          Active (shows in pickers)
        </label>
      </form>
    </Modal>
  );
}
