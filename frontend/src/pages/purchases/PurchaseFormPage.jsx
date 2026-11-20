import { useEffect, useMemo } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { purchasesApi, suppliersApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import { useCompany, useLookups } from '@/hooks/useLookups';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import LineItemsEditor from '@/components/lineitems/LineItemsEditor';
import { emptyMaterialLine } from '@/components/lineitems/lineDefaults';
import TotalsPanel from '@/components/lineitems/TotalsPanel';
import { calculateDocument } from '@/utils/gst';
import { todayISO } from '@/utils/format';

const itemSchema = z
  .object({
    item_type: z.enum(['MATERIAL', 'SERVICE']),
    material: z.union([z.coerce.number(), z.literal(''), z.null()]).optional(),
    description: z.string().trim().optional(),
    hsn_code: z.string().trim().optional(),
    quantity: z.coerce.number({ invalid_type_error: 'Enter qty' }).positive('Enter qty'),
    unit: z.string().optional(),
    rate: z.coerce.number({ invalid_type_error: 'Enter rate' }).min(0, 'Invalid'),
    discount_percent: z.coerce.number().min(0).max(100).default(0),
    gst_rate: z.string(),
  })
  .refine((i) => i.item_type === 'SERVICE' || (i.material && i.material > 0), {
    message: 'Select a material',
    path: ['material'],
  })
  .refine((i) => i.item_type === 'MATERIAL' || i.description, {
    message: 'Enter a description',
    path: ['description'],
  });

const schema = z.object({
  supplier: z.coerce
    .number({ invalid_type_error: 'Select a supplier' })
    .min(1, 'Select a supplier'),
  purchase_date: z.string().min(1, 'Select the date'),
  supplier_invoice_number: z.string().trim(),
  supplier_invoice_date: z.string(),
  transport_charges: z.coerce.number().min(0),
  notes: z.string().trim(),
  receive_now: z.boolean().optional(),
  items: z.array(itemSchema).min(1, 'Add at least one item'),
});

export default function PurchaseFormPage() {
  const { id } = useParams();
  const isEdit = !!id;
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { units } = useLookups();
  const company = useCompany();
  const { data: suppliers = [], isSuccess: suppliersLoaded } = useQuery({
    queryKey: ['suppliers', 'all'],
    queryFn: () => suppliersApi.list({ page_size: 200 }).then((d) => d.results),
  });
  const { data: existing } = useQuery({
    queryKey: ['purchases', id],
    queryFn: () => purchasesApi.get(id),
    enabled: isEdit,
  });

  const {
    register,
    handleSubmit,
    control,
    setValue,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      supplier: searchParams.get('supplier') || '',
      purchase_date: todayISO(),
      supplier_invoice_number: '',
      supplier_invoice_date: '',
      transport_charges: '0',
      notes: '',
      receive_now: true,
      items: [emptyMaterialLine()],
    },
  });

  useEffect(() => {
    if (!existing) return;
    reset({
      supplier: existing.supplier,
      purchase_date: existing.purchase_date,
      supplier_invoice_number: existing.supplier_invoice_number,
      supplier_invoice_date: existing.supplier_invoice_date || '',
      transport_charges: existing.transport_charges,
      notes: existing.notes,
      items: existing.items.map((i) => ({
        item_type: i.item_type,
        material: i.material,
        description: i.description,
        hsn_code: i.hsn_code,
        quantity: i.quantity,
        unit: i.unit,
        rate: i.rate,
        discount_percent: i.discount_percent,
        gst_rate: String(Number(i.gst_rate)),
      })),
    });
  }, [existing, reset]);

  const [supplierId, items, transport] = useWatch({
    control,
    name: ['supplier', 'items', 'transport_charges'],
  });
  const supplier = suppliers.find((s) => s.id === Number(supplierId));
  const interstate = !!(supplier && company && supplier.state_code !== company.state_code);
  const calc = useMemo(
    () => calculateDocument(items || [], { interstate, extraCharges: transport }),
    [items, interstate, transport],
  );

  const onSubmit = async (values) => {
    const payload = {
      ...values,
      supplier_invoice_date: values.supplier_invoice_date || null,
      items: values.items.map((i) => ({
        ...i,
        material: i.item_type === 'MATERIAL' ? i.material : null,
      })),
    };
    if (isEdit) delete payload.receive_now;
    try {
      const saved = isEdit
        ? await purchasesApi.update(id, payload)
        : await purchasesApi.create(payload);
      qc.invalidateQueries({ queryKey: ['purchases'] });
      qc.invalidateQueries({ queryKey: ['materials'] });
      qc.invalidateQueries({ queryKey: ['suppliers'] });
      toast.success(isEdit ? 'Purchase updated' : `Purchase ${saved.po_number} saved`);
      navigate(`/purchases/${saved.id}`);
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  if (isEdit && existing && !existing.can_edit) {
    return (
      <div className="card">
        This purchase can no longer be edited (goods received or cancelled).
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <BackLink to={isEdit ? `/purchases/${id}` : '/purchases'}>
        {isEdit ? 'Back to purchase' : 'All purchases'}
      </BackLink>
      <PageHeader
        title={isEdit ? `Edit ${existing?.po_number || ''}` : 'New purchase'}
        subtitle="Material bought from a supplier"
        actions={
          <button className="btn-primary" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} {isEdit ? 'Save changes' : 'Save purchase'}
          </button>
        }
      />
      <div className="card mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Supplier" required error={errors.supplier} className="sm:col-span-2">
          <Select
            placeholder="Select supplier"
            options={suppliers.map((s) => ({
              value: s.id,
              label: `${s.name}${s.city ? ` · ${s.city}` : ''}`,
            }))}
            {...register('supplier')}
          />
          {supplier && (
            <p className="mt-1 text-xs text-slate-500">
              {interstate
                ? `Other state (${supplier.state_name}) → IGST`
                : 'Same state → CGST + SGST'}
            </p>
          )}
          {suppliersLoaded && suppliers.length === 0 && (
            <p className="mt-1 text-xs text-amber-700">
              No suppliers yet —{' '}
              <Link to="/suppliers" className="font-medium underline">
                add a supplier first
              </Link>
              .
            </p>
          )}
        </Field>
        <Field label="Purchase date" required error={errors.purchase_date}>
          <Input type="date" {...register('purchase_date')} />
        </Field>
        <Field label="Transport charges (₹)" error={errors.transport_charges}>
          <Input type="number" step="0.01" {...register('transport_charges')} />
        </Field>
        <Field label="Supplier bill no." error={errors.supplier_invoice_number}>
          <Input {...register('supplier_invoice_number')} />
        </Field>
        <Field label="Supplier bill date">
          <Input type="date" {...register('supplier_invoice_date')} />
        </Field>
        <Field label="Notes" className="sm:col-span-2">
          <Textarea rows={1} {...register('notes')} />
        </Field>
      </div>
      <h2 className="mb-2 font-semibold">Items</h2>
      <LineItemsEditor
        control={control}
        register={register}
        setValue={setValue}
        errors={errors}
        units={units}
        interstate={interstate}
        priceField="purchase_price"
      />
      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_380px]">
        <div>
          {!isEdit && (
            <label className="card flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-brand-600"
                {...register('receive_now')}
              />
              <span>
                <b>Goods received now</b> — add all material quantities to stock immediately.
                <span className="block text-xs text-slate-500">
                  Untick for a purchase order where goods will arrive later (you can receive part
                  deliveries).
                </span>
              </span>
            </label>
          )}
        </div>
        <TotalsPanel
          calc={calc}
          interstate={interstate}
          note="Final amounts are recalculated by the server when you save."
        />
      </div>
      <div className="mt-4 flex justify-end gap-2 border-t border-slate-200 pt-4 dark:border-slate-700">
        <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>
          Cancel
        </button>
        <button className="btn-primary" disabled={isSubmitting}>
          {isSubmitting && <Spinner />} {isEdit ? 'Save changes' : 'Save purchase'}
        </button>
      </div>
    </form>
  );
}
