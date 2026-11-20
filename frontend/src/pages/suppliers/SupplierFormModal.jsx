import { useEffect } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import toast from 'react-hot-toast';
import { suppliersApi } from '@/api/services';
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
    name: z.string().trim().min(2, 'Enter the supplier name'),
    contact_person: z.string().trim(),
    phone: mobile(true),
    alternate_phone: mobile(false),
    email: z
      .string()
      .trim()
      .refine((v) => v === '' || /^\S+@\S+\.\S+$/.test(v), 'Enter a valid email'),
    address: z.string().trim(),
    city: z.string().trim(),
    state_code: z.string(),
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
        'Enter a valid GSTIN',
      ),
    opening_balance: z.coerce.number().min(0),
    bank_details: z.string().trim(),
    notes: z.string().trim(),
  })
  .refine((d) => !d.gstin || d.gstin.slice(0, 2) === d.state_code, {
    message: 'GSTIN state code does not match the state',
    path: ['gstin'],
  });
const EMPTY = {
  name: '',
  contact_person: '',
  phone: '',
  alternate_phone: '',
  email: '',
  address: '',
  city: '',
  state_code: '33',
  pincode: '',
  gstin: '',
  opening_balance: '0',
  bank_details: '',
  notes: '',
};

export default function SupplierFormModal({ supplier, onClose, onSaved }) {
  const isEdit = !!supplier?.id;
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
    if (supplier)
      reset(
        isEdit ? Object.fromEntries(Object.keys(EMPTY).map((k) => [k, supplier[k] ?? ''])) : EMPTY,
      );
  }, [supplier, isEdit, reset]);

  const onSubmit = async (values) => {
    try {
      const saved = isEdit
        ? await suppliersApi.update(supplier.id, values)
        : await suppliersApi.create(values);
      toast.success(isEdit ? 'Supplier updated' : 'Supplier added');
      onSaved?.(saved);
      onClose();
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  return (
    <Modal
      open={!!supplier}
      onClose={onClose}
      size="lg"
      title={isEdit ? `Edit ${supplier.name}` : 'Add supplier'}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" form="supplier-form" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} Save
          </button>
        </>
      }
    >
      <form
        id="supplier-form"
        onSubmit={handleSubmit(onSubmit)}
        className="grid gap-4 sm:grid-cols-2"
        noValidate
      >
        <Field label="Supplier / firm name" required error={errors.name}>
          <Input autoFocus {...register('name')} />
        </Field>
        <Field label="Contact person" error={errors.contact_person}>
          <Input {...register('contact_person')} />
        </Field>
        <Field label="Mobile" required error={errors.phone}>
          <Input inputMode="tel" {...register('phone')} />
        </Field>
        <Field label="Alternate mobile" error={errors.alternate_phone}>
          <Input inputMode="tel" {...register('alternate_phone')} />
        </Field>
        <Field label="Email" error={errors.email}>
          <Input type="email" {...register('email')} />
        </Field>
        <Field label="GSTIN" error={errors.gstin}>
          <Input className="uppercase" maxLength={15} {...register('gstin')} />
        </Field>
        <Field label="Address" className="sm:col-span-2">
          <Textarea rows={2} {...register('address')} />
        </Field>
        <Field label="City">
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
        <Field label="State" hint="Other state → purchases use IGST">
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
        <Field
          label="Opening balance (₹)"
          hint="What you already owed them when you started using this system"
          error={errors.opening_balance}
        >
          <Input type="number" step="0.01" {...register('opening_balance')} />
        </Field>
        <Field label="Bank details" className="sm:col-span-2">
          <Textarea rows={2} placeholder="A/c no, IFSC, UPI" {...register('bank_details')} />
        </Field>
        <Field label="Notes" className="sm:col-span-2">
          <Textarea rows={2} {...register('notes')} />
        </Field>
      </form>
    </Modal>
  );
}
