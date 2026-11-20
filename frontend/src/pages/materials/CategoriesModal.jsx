import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react';
import { categoriesApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import Modal from '@/components/ui/Modal';
import { Input } from '@/components/ui/Field';

export default function CategoriesModal({ open, onClose, canEdit }) {
  const qc = useQueryClient();
  const { data: cats = [] } = useQuery({
    queryKey: ['material-categories'],
    queryFn: () => categoriesApi.list(),
    enabled: open,
  });
  const [newName, setNewName] = useState('');
  const [editing, setEditing] = useState(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ['material-categories'] });
  const onError = (e) => toast.error(getErrorMessage(e));
  const add = useMutation({
    mutationFn: () => categoriesApi.create({ name: newName }),
    onSuccess: () => {
      setNewName('');
      refresh();
    },
    onError,
  });
  const save = useMutation({
    mutationFn: () => categoriesApi.update(editing.id, { name: editing.name }),
    onSuccess: () => {
      setEditing(null);
      refresh();
    },
    onError,
  });
  const del = useMutation({
    mutationFn: (id) => categoriesApi.remove(id),
    onSuccess: refresh,
    onError,
  });

  return (
    <Modal open={open} onClose={onClose} title="Material categories" size="sm">
      {canEdit && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (newName.trim()) add.mutate();
          }}
          className="mb-3 flex gap-2"
        >
          <Input
            placeholder="New category (e.g. Plywood)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button
            className="btn-primary px-3"
            disabled={!newName.trim() || add.isPending}
            aria-label="Add category"
          >
            <Plus size={16} />
          </button>
        </form>
      )}
      <ul className="divide-y divide-slate-100 dark:divide-slate-700">
        {cats.map((c) => (
          <li key={c.id} className="flex items-center gap-2 py-2">
            {editing?.id === c.id ? (
              <>
                <Input
                  value={editing.name}
                  onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                  autoFocus
                />
                <button className="btn-ghost" onClick={() => save.mutate()} aria-label="Save">
                  <Check size={16} />
                </button>
                <button className="btn-ghost" onClick={() => setEditing(null)} aria-label="Cancel">
                  <X size={16} />
                </button>
              </>
            ) : (
              <>
                <span className="flex-1 text-sm">{c.name}</span>
                <span className="text-xs text-slate-500">{c.material_count} items</span>
                {canEdit && (
                  <>
                    <button
                      className="btn-ghost"
                      onClick={() => setEditing({ id: c.id, name: c.name })}
                      aria-label={`Rename ${c.name}`}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      className="btn-ghost text-red-600"
                      disabled={c.material_count > 0}
                      title={c.material_count ? 'Has materials' : 'Delete'}
                      onClick={() => del.mutate(c.id)}
                      aria-label={`Delete ${c.name}`}
                    >
                      <Trash2 size={15} />
                    </button>
                  </>
                )}
              </>
            )}
          </li>
        ))}
      </ul>
    </Modal>
  );
}
