import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { authApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import AuthShell from '@/components/auth/AuthShell';
import PasswordInput from '@/components/auth/PasswordInput';
import { Field } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';
import { newPasswordPair } from '@/utils/validation';

export default function ResetPassword() {
  const { uid, token } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(newPasswordPair) });

  const onSubmit = async (values) => {
    setError('');
    try {
      await authApi.resetPassword({ uid, token, ...values });
      toast.success('Password reset. Please log in.');
      navigate('/login', { replace: true });
    } catch (e) {
      setError(getErrorMessage(e));
    }
  };

  return (
    <AuthShell title="Set a new password">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {error && (
          <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        )}
        <Field
          label="New password"
          error={errors.new_password}
          hint="At least 8 characters, not only numbers"
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
        <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
          {isSubmitting && <Spinner />} Reset password
        </button>
        <p className="text-center text-sm">
          <Link to="/forgot-password" className="text-brand-600 hover:underline">
            Request a new link
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
