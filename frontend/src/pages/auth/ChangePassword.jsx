import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ShieldAlert } from 'lucide-react';
import { authApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import PasswordInput from '@/components/auth/PasswordInput';
import { Field } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import PageHeader from '@/components/ui/PageHeader';
import { passwordSchema } from '@/utils/validation';

const schema = z
  .object({
    old_password: z.string().min(1, 'Enter your current password'),
    new_password: passwordSchema,
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })
  .refine((d) => d.new_password !== d.old_password, {
    message: 'New password must be different',
    path: ['new_password'],
  });

export default function ChangePassword() {
  const { user, applySession, logout } = useAuth();
  const navigate = useNavigate();
  const forced = !!user?.must_change_password;
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });

  const onSubmit = async (values) => {
    try {
      const data = await authApi.changePassword(values);
      applySession(data);
      toast.success('Password changed. Other devices have been logged out.');
      navigate('/', { replace: true });
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <PageHeader title="Change password" />
      {forced && (
        <div className="mb-4 flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200">
          <ShieldAlert size={18} className="mt-0.5 shrink-0" />
          You are using a temporary password. Please set your own password to continue.
        </div>
      )}
      <form onSubmit={handleSubmit(onSubmit)} className="card space-y-4" noValidate>
        <Field
          label={forced ? 'Temporary password' : 'Current password'}
          error={errors.old_password}
        >
          <PasswordInput
            autoComplete="current-password"
            invalid={!!errors.old_password}
            {...register('old_password')}
          />
        </Field>
        <Field
          label="New password"
          error={errors.new_password}
          hint="At least 8 characters, not only numbers, not similar to your name"
        >
          <PasswordInput
            autoComplete="new-password"
            invalid={!!errors.new_password}
            {...register('new_password')}
          />
        </Field>
        <Field label="Confirm new password" error={errors.confirm_password}>
          <PasswordInput
            autoComplete="new-password"
            invalid={!!errors.confirm_password}
            {...register('confirm_password')}
          />
        </Field>
        <div className="flex gap-2">
          <button type="submit" className="btn-primary flex-1" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} Change password
          </button>
          {forced && (
            <button type="button" className="btn-secondary" onClick={logout}>
              Log out
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
