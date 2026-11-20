import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { KeyRound } from 'lucide-react';
import { authApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import PageHeader from '@/components/ui/PageHeader';
import { Field, Input } from '@/components/ui/Field';
import Badge from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import { formatDateTime } from '@/utils/format';
import { phoneSchema } from '@/utils/validation';

const schema = z.object({
  first_name: z.string().trim().min(1, 'Enter your first name'),
  last_name: z.string().trim(),
  email: z.string().trim().email('Enter a valid email'),
  phone: phoneSchema,
});

export default function Profile() {
  const { user, setUser } = useAuth();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting, isDirty },
    reset,
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      phone: user.phone,
    },
  });

  const onSubmit = async (values) => {
    try {
      const updated = await authApi.updateMe(values);
      setUser(updated);
      reset(values);
      toast.success('Profile updated');
    } catch (e) {
      if (!applyFieldErrors(e, setError)) toast.error(getErrorMessage(e));
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="My profile"
        actions={
          <Link to="/change-password" className="btn-secondary">
            <KeyRound size={16} /> Change password
          </Link>
        }
      />
      <div className="card mb-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div>
          <p className="text-slate-500">Username</p>
          <p className="font-medium">{user.username}</p>
        </div>
        <div>
          <p className="text-slate-500">Role</p>
          <Badge color="orange">{user.role_name || user.role_code}</Badge>
        </div>
        <div>
          <p className="text-slate-500">Last login</p>
          <p>{formatDateTime(user.last_login) || '—'}</p>
        </div>
        <div>
          <p className="text-slate-500">Member since</p>
          <p>{formatDateTime(user.date_joined).split(' ')[0]}</p>
        </div>
      </div>
      <form onSubmit={handleSubmit(onSubmit)} className="card grid gap-4 sm:grid-cols-2" noValidate>
        <Field label="First name" required error={errors.first_name}>
          <Input {...register('first_name')} />
        </Field>
        <Field label="Last name" error={errors.last_name}>
          <Input {...register('last_name')} />
        </Field>
        <Field label="Email" required error={errors.email}>
          <Input type="email" {...register('email')} />
        </Field>
        <Field label="Mobile" error={errors.phone}>
          <Input inputMode="numeric" maxLength={10} {...register('phone')} />
        </Field>
        <div className="sm:col-span-2">
          <button className="btn-primary" disabled={isSubmitting || !isDirty}>
            {isSubmitting && <Spinner />} Save changes
          </button>
        </div>
      </form>
    </div>
  );
}
