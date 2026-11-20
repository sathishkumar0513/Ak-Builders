import { useEffect, useMemo } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { customersApi, quotationsApi, termsApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import { useCompany, useLookups } from '@/hooks/useLookups';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import { Field, Input, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import CustomerPicker from '@/components/CustomerPicker';
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

const schema = z
  .object({
    customer: z.coerce
      .number({ invalid_type_error: 'Select a customer' })
      .min(1, 'Select a customer'),
    title: z.string().trim().max(200),
    site_address: z.string().trim(),
    quotation_date: z.string().min(1, 'Select the date'),
    valid_until: z.string().min(1, 'Select the validity date'),
    header_discount: z.coerce.number().min(0, 'Cannot be negative'),
    terms_and_conditions: z.string(),
    notes: z.string().trim(),
    items: z.array(itemSchema).min(1, 'Add at least one item'),
  })
  .refine((d) => d.valid_until >= d.quotation_date, {
    message: 'Must be on or after the quotation date',
    path: ['valid_until'],
  });

const addDays = (iso, days) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export default function QuotationFormPage() {
  const { id } = useParams();
  const isEdit = !!id;
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { units } = useLookups();
  const company = useCompany();
  const { data: existing } = useQuery({
    queryKey: ['quotations', id],
    queryFn: () => quotationsApi.get(id),
    enabled: isEdit,
  });
  const { data: templates = [] } = useQuery({
    queryKey: ['terms', 'QUOTATION'],
    queryFn: () => termsApi.list({ applies_to: 'QUOTATION' }),
  });

  const validity = company?.quotation_validity_days || 15;
  const {
    register,
    handleSubmit,
    control,
    setValue,
    reset,
    getValues,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      customer: searchParams.get('customer') || '',
      title: '',
      site_address: '',
      quotation_date: todayISO(),
      valid_until: addDays(todayISO(), 15),
      header_discount: '0',
      terms_and_conditions: '',
      notes: '',
      items: [emptyMaterialLine()],
    },
  });

  // fill validity from company settings and default terms (new quotation only)
  useEffect(() => {
    if (!isEdit && company) setValue('valid_until', addDays(getValues('quotation_date'), validity));
  }, [company, isEdit, setValue, getValues, validity]);
  useEffect(() => {
    if (!isEdit && templates.length && !getValues('terms_and_conditions')) {
      setValue(
        'terms_and_conditions',
        (templates.find((t) => t.is_default) || templates[0]).content,
      );
    }
  }, [templates, isEdit, getValues, setValue]);

  useEffect(() => {
    if (!existing) return;
    reset({
      customer: existing.customer,
      title: existing.title,
      site_address: existing.site_address,
      quotation_date: existing.quotation_date,
      valid_until: existing.valid_until,
      header_discount: existing.header_discount,
      terms_and_conditions: existing.terms_and_conditions,
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

  const [customerId, items, headerDiscount] = useWatch({
    control,
    name: ['customer', 'items', 'header_discount'],
  });
  const { data: customer } = useQuery({
    queryKey: ['customers', String(customerId)],
    queryFn: () => customersApi.get(customerId),
    enabled: !!customerId,
  });
  const interstate = !!(customer && company && customer.state_code !== company.state_code);
  const calc = useMemo(
    () => calculateDocument(items || [], { interstate, headerDiscount }),
    [items, interstate, headerDiscount],
  );

  const onSubmit = async (values) => {
    const payload = {
      ...values,
      items: values.items.map((i) => ({
        ...i,
        material: i.item_type === 'MATERIAL' ? i.material : null,
      })),
    };
    try {
      const saved = isEdit
        ? await quotationsApi.update(id, payload)
        : await quotationsApi.create(payload);
      qc.setQueryData(['quotations', String(saved.id)], saved);
      qc.invalidateQueries({ queryKey: ['quotations'], refetchType: 'none' });
      qc.invalidateQueries({ queryKey: ['customers'] });
      toast.success(isEdit ? 'Quotation updated' : `Quotation ${saved.number} created`);
      navigate(`/quotations/${saved.id}`);
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  if (isEdit && existing && !existing.allowed_actions.includes('edit')) {
    return (
      <div className="card">
        Only draft quotations can be edited. Open the quotation and use <b>Revise</b> to make
        changes.
      </div>
    );
  }
  const saveBtn = (
    <button className="btn-primary" disabled={isSubmitting}>
      {isSubmitting && <Spinner />} {isEdit ? 'Save changes' : 'Save quotation'}
    </button>
  );

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <BackLink to={isEdit ? `/quotations/${id}` : '/quotations'}>
        {isEdit ? 'Back to quotation' : 'All quotations'}
      </BackLink>
      <PageHeader
        title={
          isEdit
            ? `Edit ${existing?.number || ''} Rev ${existing?.revision || ''}`
            : 'New quotation'
        }
        subtitle="Materials, labour and work items with GST"
        actions={saveBtn}
      />
      <div className="card mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Customer" required error={errors.customer} className="sm:col-span-2">
          <Controller
            control={control}
            name="customer"
            render={({ field }) => (
              <CustomerPicker
                value={field.value}
                invalid={!!errors.customer}
                onChange={(c) => {
                  field.onChange(c.id);
                  if (!getValues('site_address')) setValue('site_address', c.address || '');
                }}
              />
            )}
          />
          {customer && (
            <p className="mt-1 text-xs text-slate-500">
              {interstate
                ? `Other state (${customer.state_name}) → IGST`
                : 'Tamil Nadu → CGST + SGST'}
              {customer.gstin && ` · GSTIN ${customer.gstin}`}
            </p>
          )}
        </Field>
        <Field label="Quotation date" required error={errors.quotation_date}>
          <Input
            type="date"
            {...register('quotation_date', {
              onChange: (e) => setValue('valid_until', addDays(e.target.value, validity)),
            })}
          />
        </Field>
        <Field label="Valid until" required error={errors.valid_until}>
          <Input type="date" {...register('valid_until')} />
        </Field>
        <Field label="Title / work description" error={errors.title} className="sm:col-span-2">
          <Input
            placeholder="e.g. Kitchen & hall renovation – ground floor"
            {...register('title')}
          />
        </Field>
        <Field
          label="Site address"
          error={errors.site_address}
          className="sm:col-span-2"
          hint="Defaults to the customer's address"
        >
          <Textarea rows={1} {...register('site_address')} />
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
        priceField="selling_price"
        headerDiscount={headerDiscount}
      />

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="card space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <label className="label mb-0">Terms &amp; conditions</label>
            {templates.length > 0 && (
              <select
                className="input w-auto py-1 text-xs"
                defaultValue=""
                onChange={(e) => {
                  const t = templates.find((x) => String(x.id) === e.target.value);
                  if (t) setValue('terms_and_conditions', t.content, { shouldDirty: true });
                  e.target.value = '';
                }}
              >
                <option value="">Use a template…</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                    {t.is_default ? ' (default)' : ''}
                  </option>
                ))}
              </select>
            )}
          </div>
          <Textarea rows={6} {...register('terms_and_conditions')} />
          <Field label="Notes (printed on the quotation)">
            <Textarea rows={2} {...register('notes')} />
          </Field>
        </div>
        <div className="space-y-3">
          <Field
            label="Overall discount (₹)"
            error={errors.header_discount}
            hint="Applied before GST, spread across all lines"
            className="card"
          >
            <Input type="number" step="0.01" inputMode="decimal" {...register('header_discount')} />
          </Field>
          <TotalsPanel
            calc={calc}
            interstate={interstate}
            note="Final amounts are recalculated by the server when you save."
          />
        </div>
      </div>
      <div className="mt-4 flex justify-end gap-2 border-t border-slate-200 pt-4 dark:border-slate-700">
        <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>
          Cancel
        </button>
        {saveBtn}
      </div>
    </form>
  );
}
