import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { getErrorMessage } from '@/api/client';
import AuthShell from '@/components/auth/AuthShell';
import PasswordInput from '@/components/auth/PasswordInput';
import { Field, Input } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';

const schema = z.object({
  username: z.string().trim().min(1, 'Enter your username or email'),
  password: z.string().min(1, 'Enter your password'),
});

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState('');
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });

  const onSubmit = async ({ username, password }) => {
    setError('');
    try {
      const user = await login(username, password);
      toast.success(`Welcome, ${user.first_name || user.username}`);
      const dest = user.must_change_password
        ? '/change-password'
        : location.state?.from?.pathname || '/';
      navigate(dest, { replace: true });
    } catch (e) {
      setError(getErrorMessage(e));
    }
  };

  return (
    <AuthShell title="AK Builders" subtitle="Sign in to continue">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {error && (
          <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
            {error}
          </div>
        )}
        <Field label="Username or email" error={errors.username}>
          <Input
            autoComplete="username"
            autoFocus
            invalid={!!errors.username}
            {...register('username')}
          />
        </Field>
        <Field label="Password" error={errors.password}>
          <PasswordInput
            autoComplete="current-password"
            invalid={!!errors.password}
            {...register('password')}
          />
        </Field>
        <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
          {isSubmitting && <Spinner />} Sign in
        </button>
        <p className="text-center text-sm">
          <Link to="/forgot-password" className="text-brand-600 hover:underline">
            Forgot password?
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
