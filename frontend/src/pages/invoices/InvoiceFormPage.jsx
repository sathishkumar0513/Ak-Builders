import { useEffect, useMemo } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { customersApi, invoicesApi, projectsApi, termsApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import { useCompany, useLookups } from '@/hooks/useLookups';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import CustomerPicker from '@/components/CustomerPicker';
import LineItemsEditor from '@/components/lineitems/LineItemsEditor';
import { emptyMaterialLine } from '@/components/lineitems/lineDefaults';
import TotalsPanel from '@/components/lineitems/TotalsPanel';
import { calculateDocument } from '@/utils/gst';
import { formatINR, todayISO } from '@/utils/format';

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
    project: z.union([z.coerce.number(), z.literal('')]).optional(),
    quotation: z.union([z.coerce.number(), z.literal(''), z.null()]).optional(),
    invoice_date: z.string().min(1, 'Select the date'),
    due_date: z.string().min(1, 'Select the due date'),
    header_discount: z.coerce.number().min(0),
    terms_and_conditions: z.string(),
    notes: z.string().trim(),
    auto_adjust_advance: z.boolean(),
    deduct_stock: z.boolean(),
    items: z.array(itemSchema).min(1, 'Add at least one item'),
  })
  .refine((d) => d.due_date >= d.invoice_date, {
    message: 'Must be on or after the invoice date',
    path: ['due_date'],
  });

const addDays = (iso, days) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export default function InvoiceFormPage() {
  const { id } = useParams();
  const isEdit = !!id;
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { units } = useLookups();
  const company = useCompany();
  const dueDays = company?.invoice_due_days ?? 7;
  const fromQuotation = sp.get('quotation');
  const { data: existing } = useQuery({
    queryKey: ['invoices', id],
    queryFn: () => invoicesApi.get(id),
    enabled: isEdit,
  });
  const { data: prefill } = useQuery({
    queryKey: ['invoices', 'prefill', fromQuotation],
    queryFn: () => invoicesApi.collection('prefill', { quotation: fromQuotation }),
    enabled: !!fromQuotation,
  });
  const { data: templates = [] } = useQuery({
    queryKey: ['terms', 'INVOICE'],
    queryFn: () => termsApi.list({ applies_to: 'INVOICE' }),
  });

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
      customer: sp.get('customer') || '',
      project: sp.get('project') || '',
      quotation: '',
      invoice_date: todayISO(),
      due_date: addDays(todayISO(), 7),
      header_discount: '0',
      terms_and_conditions: '',
      notes: '',
      auto_adjust_advance: true,
      deduct_stock: false,
      items: [emptyMaterialLine()],
    },
  });

  useEffect(() => {
    if (!isEdit && company) setValue('due_date', addDays(getValues('invoice_date'), dueDays));
  }, [company, isEdit, dueDays, getValues, setValue]);
  useEffect(() => {
    if (!isEdit && templates.length && !getValues('terms_and_conditions'))
      setValue(
        'terms_and_conditions',
        (templates.find((t) => t.is_default) || templates[0]).content,
      );
  }, [templates, isEdit, getValues, setValue]);
  useEffect(() => {
    if (!prefill) return;
    setValue('customer', prefill.customer);
    setValue('project', prefill.project || '');
    setValue('quotation', prefill.quotation);
    setValue('header_discount', prefill.header_discount);
    setValue(
      'items',
      prefill.items.map((i) => ({ ...i, gst_rate: String(Number(i.gst_rate)) })),
    );
  }, [prefill, setValue]);
  useEffect(() => {
    if (!existing) return;
    reset({
      customer: existing.customer,
      project: existing.project || '',
      quotation: existing.quotation,
      invoice_date: existing.invoice_date,
      due_date: existing.due_date || existing.invoice_date,
      header_discount: existing.header_discount,
      terms_and_conditions: existing.terms_and_conditions,
      notes: existing.notes,
      auto_adjust_advance: false,
      deduct_stock: existing.deduct_stock,
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

  const [customerId, projectId, items, headerDiscount] = useWatch({
    control,
    name: ['customer', 'project', 'items', 'header_discount'],
  });
  const { data: customer } = useQuery({
    queryKey: ['customers', String(customerId)],
    queryFn: () => customersApi.get(customerId),
    enabled: !!customerId,
  });
  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'of', String(customerId)],
    queryFn: () =>
      projectsApi.list({ customer: customerId, page_size: 100 }).then((d) => d.results),
    enabled: !!customerId,
  });
  const { data: openItems } = useQuery({
    queryKey: ['customers', String(customerId), 'open-items'],
    queryFn: () => customersApi.detail(customerId, 'open-items'),
    enabled: !!customerId && !isEdit,
  });
  const interstate = !!(customer && company && customer.state_code !== company.state_code);
  const calc = useMemo(
    () => calculateDocument(items || [], { interstate, headerDiscount }),
    [items, interstate, headerDiscount],
  );
  const advanceAvailable = (openItems?.advances || [])
    .filter((a) => !a.project || String(a.project) === String(projectId))
    .reduce((s, a) => s + Number(a.balance), 0);

  const onSubmit = async (values) => {
    const payload = {
      ...values,
      project: values.project || null,
      quotation: values.quotation || null,
      items: values.items.map((i) => ({
        ...i,
        material: i.item_type === 'MATERIAL' ? i.material : null,
      })),
    };
    if (isEdit) delete payload.auto_adjust_advance;
    try {
      const saved = isEdit
        ? await invoicesApi.update(id, payload)
        : await invoicesApi.create(payload);
      qc.setQueryData(['invoices', String(saved.id)], saved);
      ['invoices', 'customers', 'advances', 'projects', 'materials'].forEach((k) =>
        qc.invalidateQueries({ queryKey: [k], refetchType: 'none' }),
      );
      toast.success(
        isEdit
          ? 'Invoice updated'
          : `Invoice ${saved.number} created${Number(saved.advance_adjusted) ? ` · ${formatINR(saved.advance_adjusted)} advance adjusted` : ''}`,
      );
      navigate(`/invoices/${saved.id}`);
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  if (isEdit && existing && !existing.can_edit)
    return (
      <div className="card">
        Only an unpaid invoice with no advance adjusted can be edited. Cancel it and create a new
        one instead.
      </div>
    );
  const saveBtn = (
    <button className="btn-primary" disabled={isSubmitting}>
      {isSubmitting && <Spinner />} {isEdit ? 'Save changes' : 'Create invoice'}
    </button>
  );

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <BackLink to={isEdit ? `/invoices/${id}` : '/invoices'}>
        {isEdit ? 'Back to invoice' : 'All invoices'}
      </BackLink>
      <PageHeader
        title={isEdit ? `Edit ${existing?.number || ''}` : 'New tax invoice'}
        subtitle={
          prefill
            ? `From quotation ${prefill.title || ''}`
            : 'Invoice number is assigned when you save'
        }
        actions={saveBtn}
      />
      <div className="card mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Customer" required error={errors.customer} className="sm:col-span-2">
          {isEdit ? (
            <Input disabled value={existing?.customer_detail.name || ''} />
          ) : (
            <Controller
              control={control}
              name="customer"
              render={({ field }) => (
                <CustomerPicker
                  value={field.value}
                  invalid={!!errors.customer}
                  onChange={(c) => {
                    field.onChange(c.id);
                    setValue('project', '');
                  }}
                />
              )}
            />
          )}
          {customer && (
            <p className="mt-1 text-xs text-slate-500">
              {interstate
                ? `Other state (${customer.state_name}) → IGST`
                : 'Tamil Nadu → CGST + SGST'}
              {customer.gstin ? ` · GSTIN ${customer.gstin}` : ' · No GSTIN (B2C)'}
            </p>
          )}
        </Field>
        <Field label="Invoice date" required error={errors.invoice_date}>
          <Input
            type="date"
            {...register('invoice_date', {
              onChange: (e) => setValue('due_date', addDays(e.target.value, dueDays)),
            })}
          />
        </Field>
        <Field label="Due date" required error={errors.due_date}>
          <Input type="date" {...register('due_date')} />
        </Field>
        <Field label="Project (optional)" className="sm:col-span-2" error={errors.project}>
          <Select
            placeholder="No project — direct sale"
            {...register('project')}
            options={projects.map((p) => ({ value: p.id, label: `${p.code} · ${p.name}` }))}
          />
        </Field>
        <div className="space-y-2 text-sm sm:col-span-2">
          {!isEdit && (
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-0.5 accent-brand-600"
                {...register('auto_adjust_advance')}
              />
              <span>
                Adjust unused advance automatically{' '}
                {advanceAvailable > 0 ? (
                  <b className="text-green-700">({formatINR(advanceAvailable)} available)</b>
                ) : (
                  <span className="text-slate-500">(none available)</span>
                )}
              </span>
            </label>
          )}
          {!projectId && (
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-0.5 accent-brand-600"
                {...register('deduct_stock')}
              />
              <span>
                Material sold from the store — reduce stock{' '}
                <span className="block text-xs text-slate-500">
                  Leave unticked if the material was already issued to a site.
                </span>
              </span>
            </label>
          )}
          {errors.deduct_stock && (
            <p className="text-xs text-red-600">{errors.deduct_stock.message}</p>
          )}
        </div>
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
                  if (t) setValue('terms_and_conditions', t.content);
                  e.target.value = '';
                }}
              >
                <option value="">Use a template…</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>
            )}
          </div>
          <Textarea rows={5} {...register('terms_and_conditions')} />
          <Field label="Notes (printed on the invoice)">
            <Textarea rows={2} {...register('notes')} />
          </Field>
        </div>
        <div className="space-y-3">
          <Field label="Overall discount (₹)" error={errors.header_discount} className="card">
            <Input type="number" step="0.01" {...register('header_discount')} />
          </Field>
          <TotalsPanel
            calc={calc}
            interstate={interstate}
            note="Advance adjustment and final totals are applied by the server when you save."
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
