import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { MailCheck } from 'lucide-react';
import { authApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import AuthShell from '@/components/auth/AuthShell';
import { Field, Input } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';

const schema = z.object({ email: z.string().trim().email('Enter a valid email address') });

export default function ForgotPassword() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });

  const onSubmit = async ({ email }) => {
    setError('');
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch (e) {
      setError(getErrorMessage(e));
    }
  };

  return (
    <AuthShell
      title="Forgot password"
      subtitle={sent ? null : 'We will email you a link to set a new password.'}
    >
      {sent ? (
        <div className="space-y-4 text-center">
          <MailCheck className="mx-auto text-green-600" size={40} />
          <p className="text-sm text-slate-600 dark:text-slate-300">
            If this email is registered, a reset link has been sent. The link is valid for 2 hours.
          </p>
          <Link to="/login" className="btn-secondary w-full">
            Back to login
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          )}
          <Field label="Email" error={errors.email}>
            <Input
              type="email"
              autoComplete="email"
              autoFocus
              invalid={!!errors.email}
              {...register('email')}
            />
          </Field>
          <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} Send reset link
          </button>
          <p className="text-center text-sm">
            <Link to="/login" className="text-brand-600 hover:underline">
              Back to login
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}
