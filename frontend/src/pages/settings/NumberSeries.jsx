import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Pencil } from 'lucide-react';
import { settingsApi } from '@/api/services';
import DataTable from '@/components/ui/DataTable';
import Modal from '@/components/ui/Modal';
import { Field, Input } from '@/components/ui/Field';
import Spinner from '@/components/ui/Spinner';

export default function NumberSeries({ canEdit }) {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({
    queryKey: ['sequences'],
    queryFn: settingsApi.sequences,
  });
  const [editing, setEditing] = useState(null);
  const save = useMutation({
    mutationFn: (s) =>
      settingsApi.updateSequence(s.id, {
        prefix: s.prefix,
        padding: Number(s.padding),
        next_number: Number(s.next_number),
      }),
    onSuccess: () => {
      toast.success('Number series updated');
      qc.invalidateQueries({ queryKey: ['sequences'] });
      setEditing(null);
    },
  });

  const columns = [
    { key: 'doc', header: 'Document', render: (s) => s.doc_type_display },
    { key: 'fy', header: 'Financial year', render: (s) => s.financial_year },
    {
      key: 'next',
      header: 'Next number',
      render: (s) => (
        <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-700">
          {s.preview}
        </code>
      ),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (s) =>
        canEdit && (
          <button className="btn-ghost" onClick={() => setEditing({ ...s })} title="Edit">
            <Pencil size={16} />
          </button>
        ),
    },
  ];

  return (
    <>
      <p className="mb-3 text-sm text-slate-500">
        Numbers restart at 1 every financial year (April).{' '}
        {canEdit ? '' : 'Only a Super Admin can change these.'}
      </p>
      <DataTable
        columns={columns}
        rows={data}
        loading={isLoading}
        emptyText="Run seed_data to create number series."
      />
      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        size="sm"
        title={`Edit ${editing?.doc_type_display} series`}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => save.mutate(editing)}
              disabled={save.isPending}
            >
              {save.isPending && <Spinner />} Save
            </button>
          </>
        }
      >
        {editing && (
          <div className="space-y-3">
            <Field label="Prefix">
              <Input
                value={editing.prefix}
                onChange={(e) => setEditing({ ...editing, prefix: e.target.value })}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Digits">
                <Input
                  type="number"
                  min={1}
                  max={8}
                  value={editing.padding}
                  onChange={(e) => setEditing({ ...editing, padding: e.target.value })}
                />
              </Field>
              <Field label="Next number" hint="Only increase it — lowering can create duplicates">
                <Input
                  type="number"
                  min={1}
                  value={editing.next_number}
                  onChange={(e) => setEditing({ ...editing, next_number: e.target.value })}
                />
              </Field>
            </div>
            <p className="text-sm">
              Preview:{' '}
              <code>
                {editing.prefix}/{editing.financial_year}/
                {String(editing.next_number).padStart(Number(editing.padding) || 1, '0')}
              </code>
            </p>
          </div>
        )}
      </Modal>
    </>
  );
}
