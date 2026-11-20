import { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { projectsApi, usersApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import Modal from '@/components/ui/Modal';
import { CitySelect } from '@/components/LocationFields';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import CustomerPicker from '@/components/CustomerPicker';

const schema = z.object({
  name: z.string().trim().min(2, 'Enter the project name'),
  customer: z.coerce
    .number({ invalid_type_error: 'Select a customer' })
    .min(1, 'Select a customer'),
  project_type: z.string(),
  site_address: z.string().trim().min(3, 'Enter the site address'),
  site_city: z.string().trim(),
  site_pincode: z
    .string()
    .trim()
    .refine((v) => v === '' || /^\d{6}$/.test(v), '6-digit pincode'),
  contract_value: z.coerce.number().min(0),
  assigned_engineer: z.union([z.coerce.number(), z.literal('')]).optional(),
  start_date: z.string(),
  expected_end_date: z.string(),
  status: z.string(),
  description: z.string().trim(),
});
const STATUSES = [
  ['PLANNED', 'Planned'],
  ['IN_PROGRESS', 'In Progress'],
  ['ON_HOLD', 'On Hold'],
  ['COMPLETED', 'Completed'],
  ['CANCELLED', 'Cancelled'],
];
const TYPES = [
  ['RENOVATION', 'Renovation'],
  ['NEW', 'New construction'],
  ['SUPPLY', 'Material supply only'],
];
const opts = (a) => a.map(([value, label]) => ({ value, label }));

export default function ProjectFormModal({ project, onClose, onSaved }) {
  const isEdit = !!project?.id;
  const { data: engineers = [] } = useQuery({
    queryKey: ['users', 'engineers'],
    queryFn: () => usersApi.lookup({ role: 'SITE_ENGINEER' }),
    enabled: !!project,
  });
  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    getValues,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });
  useEffect(() => {
    if (!project) return;
    reset(
      isEdit
        ? {
            name: project.name,
            customer: project.customer,
            project_type: project.project_type,
            site_address: project.site_address,
            site_city: project.site_city || '',
            site_pincode: project.site_pincode || '',
            contract_value: project.contract_value,
            assigned_engineer: project.assigned_engineer || '',
            start_date: project.start_date || '',
            expected_end_date: project.expected_end_date || '',
            status: project.status,
            description: project.description || '',
          }
        : {
            name: '',
            customer: '',
            project_type: 'RENOVATION',
            site_address: '',
            site_city: '',
            site_pincode: '',
            contract_value: '0',
            assigned_engineer: '',
            start_date: '',
            expected_end_date: '',
            status: 'PLANNED',
            description: '',
          },
    );
  }, [project, isEdit, reset]);

  const onSubmit = async (v) => {
    const payload = {
      ...v,
      assigned_engineer: v.assigned_engineer || null,
      start_date: v.start_date || null,
      expected_end_date: v.expected_end_date || null,
    };
    if (!isEdit && Number(v.contract_value) > 0)
      payload.stages = [
        { name: 'Advance (on work order)', percentage: '30' },
        { name: 'Mid-work', percentage: '40' },
        { name: 'Completion & handover', percentage: '30' },
      ];
    try {
      const saved = isEdit
        ? await projectsApi.update(project.id, payload)
        : await projectsApi.create(payload);
      toast.success(isEdit ? 'Project updated' : `Project ${saved.code} created`);
      onSaved?.(saved);
      onClose();
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  return (
    <Modal
      open={!!project}
      onClose={onClose}
      size="lg"
      title={isEdit ? `Edit ${project.code}` : 'New project'}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" form="project-form" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} Save
          </button>
        </>
      }
    >
      <form
        id="project-form"
        onSubmit={handleSubmit(onSubmit)}
        className="grid gap-4 sm:grid-cols-2"
        noValidate
      >
        <Field label="Project name" required error={errors.name} className="sm:col-span-2">
          <Input {...register('name')} placeholder="e.g. Kumar residence – first floor extension" />
        </Field>
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
                  if (!getValues('site_address')) {
                    setValue('site_address', c.address || '');
                    setValue('site_city', c.city || '');
                    setValue('site_pincode', c.pincode || '');
                  }
                }}
              />
            )}
          />
        </Field>
        <Field label="Site address" required error={errors.site_address} className="sm:col-span-2">
          <Textarea rows={2} {...register('site_address')} />
        </Field>
        <Field label="Site city">
          <Controller
            control={control}
            name="site_city"
            render={({ field }) => (
              <CitySelect value={field.value} onChange={field.onChange} onBlur={field.onBlur} />
            )}
          />
        </Field>
        <Field label="Pincode" error={errors.site_pincode}>
          <Input inputMode="numeric" maxLength={6} {...register('site_pincode')} />
        </Field>
        <Field label="Type">
          <Select options={opts(TYPES)} {...register('project_type')} />
        </Field>
        <Field label="Status">
          <Select options={opts(STATUSES)} {...register('status')} />
        </Field>
        <Field
          label="Contract value (₹, incl. GST)"
          error={errors.contract_value}
          hint={
            !isEdit
              ? 'Creates 30/40/30 payment stages — editable later'
              : 'Unbilled stages are rescaled'
          }
        >
          <Input type="number" step="0.01" {...register('contract_value')} />
        </Field>
        <Field label="Site engineer">
          <Select
            placeholder="Not assigned"
            options={engineers.map((u) => ({ value: u.id, label: u.name }))}
            {...register('assigned_engineer')}
          />
        </Field>
        <Field label="Start date">
          <Input type="date" {...register('start_date')} />
        </Field>
        <Field label="Expected completion" error={errors.expected_end_date}>
          <Input type="date" {...register('expected_end_date')} />
        </Field>
        <Field label="Description / scope" className="sm:col-span-2">
          <Textarea rows={2} {...register('description')} />
        </Field>
      </form>
    </Modal>
  );
}
