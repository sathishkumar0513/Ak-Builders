import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import toast from 'react-hot-toast';
import { usersApi } from '@/api/services';
import { applyFieldErrors, getErrorMessage } from '@/api/client';
import Modal from '@/components/ui/Modal';
import { Field } from '@/components/ui/Field';
import PasswordInput from '@/components/auth/PasswordInput';
import Spinner from '@/components/ui/Spinner';
import { passwordSchema } from '@/utils/validation';

const schema = z.object({ new_password: passwordSchema });

export default function ResetPasswordModal({ user, onClose, onSaved }) {
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });
  useEffect(() => reset({ new_password: '' }), [user, reset]);

  const onSubmit = async ({ new_password }) => {
    try {
      await usersApi.resetPassword(user.id, new_password);
      toast.success(`Temporary password set for ${user.username}`);
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
      size="sm"
      title="Set temporary password"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" form="reset-form" disabled={isSubmitting}>
            {isSubmitting && <Spinner />} Set password
          </button>
        </>
      }
    >
      <form id="reset-form" onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {user?.full_name} will be logged out everywhere and must change this password at next
          login.
        </p>
        <Field label="Temporary password" error={errors.new_password}>
          <PasswordInput autoComplete="new-password" {...register('new_password')} />
        </Field>
      </form>
    </Modal>
  );
}
