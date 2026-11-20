import { useEffect, useState } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { ImagePlus, Trash2 } from 'lucide-react';
import { settingsApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import { CitySelect, StateSelect } from '@/components/LocationFields';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';

const opt = (re, msg) =>
  z
    .string()
    .trim()
    .toUpperCase()
    .refine((v) => v === '' || re.test(v), msg);
const schema = z.object({
  name: z.string().trim().min(1, 'Company name is required'),
  tagline: z.string().trim(),
  address: z.string().trim(),
  city: z.string().trim(),
  state_code: z.string().min(2, 'Select the state'),
  pincode: z
    .string()
    .trim()
    .refine((v) => v === '' || /^\d{6}$/.test(v), '6-digit pincode'),
  phone: z.string().trim(),
  email: z
    .string()
    .trim()
    .refine((v) => v === '' || /^\S+@\S+\.\S+$/.test(v), 'Enter a valid email'),
  website: z.string().trim(),
  gstin: opt(/^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/, 'Enter a valid 15-character GSTIN'),
  pan: opt(/^[A-Z]{5}\d{4}[A-Z]$/, 'Enter a valid PAN'),
  bank_name: z.string().trim(),
  bank_account_name: z.string().trim(),
  bank_account_number: z.string().trim(),
  bank_ifsc: opt(/^[A-Z]{4}0[A-Z0-9]{6}$/, 'Enter a valid IFSC'),
  bank_branch: z.string().trim(),
  upi_id: z.string().trim(),
  default_gst_rate: z.coerce.number().min(0).max(28),
  quotation_validity_days: z.coerce.number().int().min(1).max(365),
  invoice_due_days: z.coerce.number().int().min(0).max(365),
});
const FIELDS = Object.keys(schema.shape);

export default function CompanyProfileForm() {
  const qc = useQueryClient();
  const { data: company, isLoading } = useQuery({
    queryKey: ['company'],
    queryFn: settingsApi.company,
  });
  const [logoFile, setLogoFile] = useState(null);
  const {
    register,
    control,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });
  const stateCode = useWatch({ control, name: 'state_code' });

  useEffect(() => {
    if (company) reset(Object.fromEntries(FIELDS.map((f) => [f, company[f] ?? ''])));
  }, [company, reset]);

  const save = async (values, extra = {}) => {
    const fd = new FormData();
    Object.entries({ ...values, ...extra }).forEach(([k, v]) => fd.append(k, v));
    if (logoFile) fd.append('logo', logoFile);
    const updated = await settingsApi.updateCompany(fd);
    qc.setQueryData(['company'], updated);
    setLogoFile(null);
    return updated;
  };

  const onSubmit = async (values) => {
    try {
      await save(values);
      toast.success('Company profile saved');
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  const removeLogo = async () => {
    try {
      const updated = await settingsApi.updateCompany({ remove_logo: true });
      qc.setQueryData(['company'], updated);
      toast.success('Logo removed');
    } catch (e) {
      toast.error(getErrorMessage(e));
    }
  };

  if (isLoading) return <div className="card h-64 animate-pulse" />;
  const preview = logoFile ? URL.createObjectURL(logoFile) : company?.logo;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <section className="card">
        <h2 className="mb-3 font-semibold">Business details</h2>
        <div className="mb-4 flex items-center gap-4">
          <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-lg border border-dashed border-slate-300 bg-slate-50 dark:border-slate-600 dark:bg-slate-900">
            {preview ? (
              <img src={preview} alt="Company logo" className="h-full w-full object-contain" />
            ) : (
              <ImagePlus className="text-slate-400" />
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="btn-secondary cursor-pointer">
              <ImagePlus size={16} /> {company?.logo ? 'Change logo' : 'Upload logo'}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={(e) => setLogoFile(e.target.files?.[0] || null)}
              />
            </label>
            {company?.logo && !logoFile && (
              <button type="button" className="btn-ghost text-red-600" onClick={removeLogo}>
                <Trash2 size={16} /> Remove
              </button>
            )}
            {logoFile && (
              <p className="self-center text-xs text-slate-500">
                Click Save to upload {logoFile.name}
              </p>
            )}
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Company name" required error={errors.name}>
            <Input {...register('name')} />
          </Field>
          <Field label="Tagline" error={errors.tagline}>
            <Input {...register('tagline')} />
          </Field>
          <Field label="Phone" error={errors.phone}>
            <Input {...register('phone')} />
          </Field>
          <Field label="Address" error={errors.address} className="sm:col-span-2 lg:col-span-3">
            <Textarea rows={2} {...register('address')} />
          </Field>
          <Field label="City" error={errors.city}>
            <Controller
              control={control}
              name="city"
              render={({ field }) => (
                <CitySelect
                  stateCode={stateCode}
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  invalid={!!errors.city}
                />
              )}
            />
          </Field>
          <Field label="State" required error={errors.state_code}>
            <Controller
              control={control}
              name="state_code"
              render={({ field }) => (
                <StateSelect
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  invalid={!!errors.state_code}
                />
              )}
            />
          </Field>
          <Field label="Pincode" error={errors.pincode}>
            <Input inputMode="numeric" maxLength={6} {...register('pincode')} />
          </Field>
          <Field label="Email" error={errors.email}>
            <Input type="email" {...register('email')} />
          </Field>
          <Field label="Website" error={errors.website}>
            <Input placeholder="https://" {...register('website')} />
          </Field>
        </div>
      </section>

      <section className="card">
        <h2 className="mb-3 font-semibold">Tax</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="GSTIN" error={errors.gstin} hint="First 2 digits must match the state code">
            <Input className="uppercase" maxLength={15} {...register('gstin')} />
          </Field>
          <Field label="PAN" error={errors.pan}>
            <Input className="uppercase" maxLength={10} {...register('pan')} />
          </Field>
          <Field label="Default GST %" error={errors.default_gst_rate}>
            <Select
              options={[0, 5, 12, 18, 28].map((r) => ({ value: `${r}.00`, label: `${r}%` }))}
              {...register('default_gst_rate')}
            />
          </Field>
        </div>
      </section>

      <section className="card">
        <h2 className="mb-3 font-semibold">Bank & UPI (printed on invoices)</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Bank name" error={errors.bank_name}>
            <Input {...register('bank_name')} />
          </Field>
          <Field label="Account name" error={errors.bank_account_name}>
            <Input {...register('bank_account_name')} />
          </Field>
          <Field label="Account number" error={errors.bank_account_number}>
            <Input inputMode="numeric" {...register('bank_account_number')} />
          </Field>
          <Field label="IFSC" error={errors.bank_ifsc}>
            <Input className="uppercase" maxLength={11} {...register('bank_ifsc')} />
          </Field>
          <Field label="Branch" error={errors.bank_branch}>
            <Input {...register('bank_branch')} />
          </Field>
          <Field label="UPI ID" error={errors.upi_id}>
            <Input placeholder="name@bank" {...register('upi_id')} />
          </Field>
        </div>
      </section>

      <section className="card">
        <h2 className="mb-3 font-semibold">Defaults</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Quotation valid for (days)" error={errors.quotation_validity_days}>
            <Input type="number" {...register('quotation_validity_days')} />
          </Field>
          <Field label="Invoice due after (days)" error={errors.invoice_due_days}>
            <Input type="number" {...register('invoice_due_days')} />
          </Field>
        </div>
      </section>

      <div className="border-t border-slate-200 pt-4 dark:border-slate-700">
        <button className="btn-primary w-full sm:w-auto" disabled={isSubmitting}>
          {isSubmitting && <Spinner />} Save settings
        </button>
      </div>
    </form>
  );
}
