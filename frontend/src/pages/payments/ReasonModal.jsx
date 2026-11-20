import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/api/client';
import Modal from '@/components/ui/Modal';
import { Field, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';

/** Asks for a mandatory reason, then runs onConfirm(reason). */
export default function ReasonModal({
  open,
  onClose,
  title,
  description,
  confirmText = 'Confirm',
  onConfirm,
}) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setReason('');
  }, [open]);
  const go = async () => {
    setBusy(true);
    try {
      await onConfirm(reason.trim());
      onClose();
    } catch (e) {
      toast.error(getErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title={title}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Back
          </button>
          <button className="btn-danger" onClick={go} disabled={busy || reason.trim().length < 3}>
            {busy && <Spinner />} {confirmText}
          </button>
        </>
      }
    >
      {description && (
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">{description}</p>
      )}
      <Field label="Reason (required)">
        <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
      </Field>
    </Modal>
  );
}
