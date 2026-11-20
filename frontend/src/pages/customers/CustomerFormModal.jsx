import { useEffect } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import toast from 'react-hot-toast';
import { customersApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import Modal from '@/components/ui/Modal';
import { CitySelect, StateSelect } from '@/components/LocationFields';
import { Field, Input, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';

const mobile = (required) =>
  z
    .string()
    .trim()
    .refine(
      (v) => (!required && v === '') || /^(\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}$/.test(v),
      'Enter a valid 10-digit mobile number',
    );

const schema = z
  .object({
    name: z.string().trim().min(2, 'Enter the customer name'),
    customer_type: z.enum(['INDIVIDUAL', 'COMPANY']),
    contact_person: z.string().trim(),
    phone: mobile(true),
    alternate_phone: mobile(false),
    email: z
      .string()
      .trim()
      .refine((v) => v === '' || /^\S+@\S+\.\S+$/.test(v), 'Enter a valid email'),
    address: z.string().trim(),
    city: z.string().trim(),
    state_code: z.string().min(2),
    pincode: z
      .string()
      .trim()
      .refine((v) => v === '' || /^\d{6}$/.test(v), '6-digit pincode'),
    gstin: z
      .string()
      .trim()
      .toUpperCase()
      .refine(
        (v) => v === '' || /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(v),
        'Enter a valid 15-character GSTIN',
      ),
    notes: z.string().trim(),
  })
  .refine((d) => d.customer_type !== 'COMPANY' || d.contact_person, {
    message: 'Enter a contact person',
    path: ['contact_person'],
  })
  .refine((d) => !d.gstin || d.gstin.slice(0, 2) === d.state_code, {
    message: 'GSTIN state code does not match the state',
    path: ['gstin'],
  });

const EMPTY = {
  name: '',
  customer_type: 'INDIVIDUAL',
  contact_person: '',
  phone: '',
  alternate_phone: '',
  email: '',
  address: '',
  city: '',
  state_code: '33',
  pincode: '',
  gstin: '',
  notes: '',
};

export default function CustomerFormModal({ customer, onClose, onSaved }) {
  const isEdit = !!customer?.id;
  const {
    register,
    handleSubmit,
    reset,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });
  const stateCode = useWatch({ control, name: 'state_code' });
  const type = useWatch({ control, name: 'customer_type' });

  useEffect(() => {
    if (customer)
      reset(
        isEdit ? Object.fromEntries(Object.keys(EMPTY).map((k) => [k, customer[k] ?? ''])) : EMPTY,
      );
  }, [customer, isEdit, reset]);

  const onSubmit = async (values) => {
    try {
      const saved = isEdit
        ? await customersApi.update(customer.id, values)
        : await customersApi.create(values);
      toast.success(isEdit ? 'Customer updated' : 'Customer added');
      onSaved?.(saved);
      onClose();
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  return (
    <Modal
      open={!!customer}
      onClose={onClose}
      size="lg"
      title={isEdit ? `Edit ${customer.name}` : 'Add customer'}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" form="customer-form" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} Save
          </button>
        </>
      }
    >
      <form
        id="customer-form"
        onSubmit={handleSubmit(onSubmit)}
        className="grid gap-4 sm:grid-cols-2"
        noValidate
      >
        <Field label="Customer type">
          <div className="flex gap-4 pt-2 text-sm">
            {[
              ['INDIVIDUAL', 'Individual'],
              ['COMPANY', 'Company'],
            ].map(([v, l]) => (
              <label key={v} className="flex items-center gap-2">
                <input
                  type="radio"
                  value={v}
                  className="accent-brand-600"
                  {...register('customer_type')}
                />{' '}
                {l}
              </label>
            ))}
          </div>
        </Field>
        <Field
          label={type === 'COMPANY' ? 'Company name' : 'Full name'}
          required
          error={errors.name}
        >
          <Input autoFocus {...register('name')} />
        </Field>
        {type === 'COMPANY' && (
          <Field label="Contact person" required error={errors.contact_person}>
            <Input {...register('contact_person')} />
          </Field>
        )}
        <Field label="Mobile" required error={errors.phone}>
          <Input inputMode="tel" placeholder="98765 43210" {...register('phone')} />
        </Field>
        <Field label="Alternate mobile" error={errors.alternate_phone}>
          <Input inputMode="tel" {...register('alternate_phone')} />
        </Field>
        <Field label="Email" error={errors.email}>
          <Input type="email" {...register('email')} />
        </Field>
        <Field label="Address" error={errors.address} className="sm:col-span-2">
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
        <Field label="Pincode" error={errors.pincode}>
          <Input inputMode="numeric" maxLength={6} {...register('pincode')} />
        </Field>
        <Field label="State" hint="Decides CGST+SGST (Tamil Nadu) or IGST (other states)">
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
        <Field label="GSTIN (optional)" error={errors.gstin}>
          <Input className="uppercase" maxLength={15} {...register('gstin')} />
        </Field>
        <Field label="Notes" className="sm:col-span-2">
          <Textarea rows={2} {...register('notes')} />
        </Field>
      </form>
    </Modal>
  );
}
