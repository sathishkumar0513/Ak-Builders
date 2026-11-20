import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import toast from 'react-hot-toast';
import { usersApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import Modal from '@/components/ui/Modal';
import { Field, Input, Select } from '@/components/ui/Field';
import PasswordInput from '@/components/auth/PasswordInput';
import Spinner from '@/components/ui/Spinner';
import { passwordSchema, phoneSchema } from '@/utils/validation';

const base = {
  username: z
    .string()
    .trim()
    .min(3, 'At least 3 characters')
    .regex(/^[\w.@+-]+$/, 'Letters, numbers and . @ + - _ only'),
  email: z.string().trim().email('Enter a valid email'),
  first_name: z.string().trim().min(1, 'Enter the first name'),
  last_name: z.string().trim(),
  phone: phoneSchema,
  role: z.coerce.number({ invalid_type_error: 'Select a role' }).min(1, 'Select a role'),
  is_active: z.boolean(),
};
const createSchema = z.object({ ...base, password: passwordSchema });
const editSchema = z.object(base);

export default function UserFormModal({ user, roles, onClose, onSaved }) {
  const { user: me } = useAuth();
  const isEdit = !!user?.id;
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(isEdit ? editSchema : createSchema),
  });

  useEffect(() => {
    if (!user) return;
    reset(
      isEdit
        ? {
            username: user.username,
            email: user.email,
            first_name: user.first_name,
            last_name: user.last_name,
            phone: user.phone || '',
            role: user.role,
            is_active: user.is_active,
          }
        : {
            username: '',
            email: '',
            first_name: '',
            last_name: '',
            phone: '',
            role: '',
            is_active: true,
            password: '',
          },
    );
  }, [user, isEdit, reset]);

  // Only a Super Admin may hand out the Super Admin role
  const roleOptions = roles
    .filter((r) => r.code !== 'SUPER_ADMIN' || me.role_code === 'SUPER_ADMIN')
    .map((r) => ({ value: r.id, label: r.name }));

  const onSubmit = async (values) => {
    try {
      if (isEdit) await usersApi.update(user.id, values);
      else await usersApi.create(values);
      toast.success(
        isEdit ? 'User updated' : 'User created. Share the temporary password with them.',
      );
      onSaved();
      onClose();
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  return (
    <Modal
      open={!!user}
      onClose={onClose}
      title={isEdit ? `Edit ${user.full_name}` : 'Add user'}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" form="user-form" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} {isEdit ? 'Save' : 'Create user'}
          </button>
        </>
      }
    >
      <form
        id="user-form"
        onSubmit={handleSubmit(onSubmit)}
        className="grid gap-4 sm:grid-cols-2"
        noValidate
      >
        <Field label="First name" required error={errors.first_name}>
          <Input {...register('first_name')} />
        </Field>
        <Field label="Last name" error={errors.last_name}>
          <Input {...register('last_name')} />
        </Field>
        <Field label="Username" required error={errors.username}>
          <Input autoComplete="off" {...register('username')} />
        </Field>
        <Field label="Mobile" error={errors.phone}>
          <Input inputMode="numeric" maxLength={10} {...register('phone')} />
        </Field>
        <Field label="Email" required error={errors.email} className="sm:col-span-2">
          <Input type="email" {...register('email')} />
        </Field>
        <Field label="Role" required error={errors.role}>
          <Select placeholder="Select role" options={roleOptions} {...register('role')} />
        </Field>
        {!isEdit && (
          <Field
            label="Temporary password"
            required
            error={errors.password}
            hint="They must change it at first login"
          >
            <PasswordInput autoComplete="new-password" {...register('password')} />
          </Field>
        )}
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" className="h-4 w-4 accent-brand-600" {...register('is_active')} />{' '}
          Active (can log in)
        </label>
      </form>
    </Modal>
  );
}
