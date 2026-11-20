import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Pencil, Plus, Star, Trash2 } from 'lucide-react';
import { termsApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import Modal from '@/components/ui/Modal';
import Badge from '@/components/ui/Badge';
import { Field, Input, Select, Textarea } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';

const TYPES = [
  { value: 'QUOTATION', label: 'Quotation' },
  { value: 'INVOICE', label: 'Invoice' },
  { value: 'RECEIPT', label: 'Receipt' },
];

export default function TermsTemplates({ canEdit }) {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { data = [], isLoading } = useQuery({
    queryKey: ['terms', 'all'],
    queryFn: () => termsApi.list(),
  });
  const [editing, setEditing] = useState(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ['terms'] });
  const onError = (e) => toast.error(getErrorMessage(e));
  const save = useMutation({
    mutationFn: (t) => (t.id ? termsApi.update(t.id, t) : termsApi.create(t)),
    onSuccess: () => {
      toast.success('Template saved');
      setEditing(null);
      refresh();
    },
    onError,
  });
  const del = useMutation({ mutationFn: (id) => termsApi.remove(id), onSuccess: refresh, onError });

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Reusable terms printed on quotations, invoices and receipts. The default one is filled in
          automatically.
        </p>
        {canEdit && (
          <button
            className="btn-primary"
            onClick={() =>
              setEditing({ title: '', applies_to: 'QUOTATION', content: '', is_default: false })
            }
          >
            <Plus size={16} /> Add template
          </button>
        )}
      </div>
      {isLoading ? (
        <div className="card h-32 animate-pulse" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {data.map((t) => (
            <div key={t.id} className="card">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{t.title}</p>
                  <div className="mt-1 flex gap-1">
                    <Badge>{TYPES.find((x) => x.value === t.applies_to)?.label}</Badge>
                    {t.is_default && (
                      <Badge color="orange">
                        <Star size={11} className="mr-0.5" /> Default
                      </Badge>
                    )}
                  </div>
                </div>
                {canEdit && (
                  <div className="flex">
                    <button
                      className="btn-ghost"
                      onClick={() => setEditing({ ...t })}
                      aria-label={`Edit ${t.title}`}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      className="btn-ghost text-red-600"
                      aria-label={`Delete ${t.title}`}
                      onClick={async () => {
                        if (
                          await confirm({
                            title: 'Delete template?',
                            message: t.title,
                            confirmText: 'Delete',
                            danger: true,
                          })
                        )
                          del.mutate(t.id);
                      }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                )}
              </div>
              <p className="line-clamp-6 whitespace-pre-line text-xs text-slate-600 dark:text-slate-300">
                {t.content}
              </p>
            </div>
          ))}
        </div>
      )}
      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        size="lg"
        title={editing?.id ? 'Edit template' : 'Add template'}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              disabled={save.isPending || !editing?.title || !editing?.content}
              onClick={() => save.mutate(editing)}
            >
              {save.isPending && <Spinner />} Save
            </button>
          </>
        }
      >
        {editing && (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Title">
                <Input
                  value={editing.title}
                  onChange={(e) => setEditing({ ...editing, title: e.target.value })}
                />
              </Field>
              <Field label="Used for">
                <Select
                  value={editing.applies_to}
                  options={TYPES}
                  onChange={(e) => setEditing({ ...editing, applies_to: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Terms (one per line)">
              <Textarea
                rows={10}
                value={editing.content}
                onChange={(e) => setEditing({ ...editing, content: e.target.value })}
              />
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="accent-brand-600"
                checked={editing.is_default}
                onChange={(e) => setEditing({ ...editing, is_default: e.target.checked })}
              />{' '}
              Use as the default for this document type
            </label>
          </div>
        )}
      </Modal>
    </>
  );
}
