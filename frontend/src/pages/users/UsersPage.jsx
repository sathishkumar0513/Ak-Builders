import { useState } from 'react';
import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Download, KeyRound, Pencil, Plus, Power, Trash2 } from 'lucide-react';
import { usersApi } from '@/api/services';
import { useAuth } from '@/context/AuthContext';
import { useListParams } from '@/hooks/useListParams';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Select } from '@/components/ui/Field';
import { exportCsv } from '@/utils/exportCsv';
import { formatDateTime } from '@/utils/format';
import UserFormModal from './UserFormModal';
import ResetPasswordModal from './ResetPasswordModal';

const ROLE_COLORS = {
  SUPER_ADMIN: 'purple',
  ADMIN: 'orange',
  ACCOUNTANT: 'blue',
  SITE_ENGINEER: 'amber',
  SALES: 'green',
};

export default function UsersPage() {
  const { user: me } = useAuth();
  const confirm = useConfirm();
  const qc = useQueryClient();
  const { params, setParams, toggleOrdering } = useListParams({ ordering: 'username' });
  const [editing, setEditing] = useState(null); // null = closed, {} = new, user = edit
  const [resetting, setResetting] = useState(null);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['users', params],
    queryFn: () => usersApi.list(params),
    placeholderData: keepPreviousData,
  });
  const { data: roles = [] } = useQuery({
    queryKey: ['roles'],
    queryFn: usersApi.roles,
    staleTime: Infinity,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['users'] });
  const toggleActive = useMutation({
    mutationFn: (u) => (u.is_active ? usersApi.deactivate(u.id) : usersApi.activate(u.id)),
    onSuccess: (u) => {
      toast.success(`${u.username} ${u.is_active ? 'activated' : 'deactivated'}`);
      invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (u) => usersApi.remove(u.id),
    onSuccess: () => {
      toast.success('User deleted');
      invalidate();
    },
  });

  const canTouch = (u) =>
    u.id !== me.id && (u.role_code !== 'SUPER_ADMIN' || me.role_code === 'SUPER_ADMIN');

  const onToggle = async (u) => {
    const ok = await confirm({
      title: u.is_active ? 'Deactivate user?' : 'Activate user?',
      message: u.is_active
        ? `${u.full_name} will be logged out on all devices and cannot log in until activated again.`
        : `${u.full_name} will be able to log in again.`,
      confirmText: u.is_active ? 'Deactivate' : 'Activate',
      danger: u.is_active,
    });
    if (ok) toggleActive.mutate(u);
  };

  const onDelete = async (u) => {
    const ok = await confirm({
      title: 'Delete user?',
      message: `${u.full_name} (${u.username}) will be removed from the list and can no longer log in. Their past records stay intact.`,
      confirmText: 'Delete',
      danger: true,
    });
    if (ok) remove.mutate(u);
  };

  const onExport = async () => {
    const all = await usersApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-users',
      [
        { header: 'Username', value: (u) => u.username },
        { header: 'Name', value: (u) => u.full_name },
        { header: 'Email', value: (u) => u.email },
        { header: 'Mobile', value: (u) => u.phone },
        { header: 'Role', value: (u) => u.role_name },
        { header: 'Status', value: (u) => (u.is_active ? 'Active' : 'Inactive') },
        { header: 'Last login', value: (u) => formatDateTime(u.last_login) },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'username',
      header: 'User',
      sortField: 'username',
      render: (u) => (
        <div>
          <p className="font-medium">{u.full_name}</p>
          <p className="text-xs text-slate-500">@{u.username}</p>
        </div>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      sortField: 'email',
      render: (u) => <span className="break-all">{u.email}</span>,
    },
    { key: 'phone', header: 'Mobile', render: (u) => u.phone || '—' },
    {
      key: 'role',
      header: 'Role',
      render: (u) => <Badge color={ROLE_COLORS[u.role_code]}>{u.role_name || 'No role'}</Badge>,
    },
    {
      key: 'status',
      header: 'Status',
      sortField: 'is_active',
      render: (u) => (
        <div className="flex flex-wrap gap-1">
          <Badge color={u.is_active ? 'green' : 'red'}>{u.is_active ? 'Active' : 'Inactive'}</Badge>
          {u.must_change_password && <Badge color="amber">Temp password</Badge>}
        </div>
      ),
    },
    {
      key: 'last_login',
      header: 'Last login',
      sortField: 'last_login',
      render: (u) => formatDateTime(u.last_login) || 'Never',
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (u) =>
        canTouch(u) ? (
          <div className="flex justify-end gap-1">
            <button className="btn-ghost" title="Edit" onClick={() => setEditing(u)}>
              <Pencil size={16} />
            </button>
            <button
              className="btn-ghost"
              title="Set temporary password"
              onClick={() => setResetting(u)}
            >
              <KeyRound size={16} />
            </button>
            <button
              className="btn-ghost"
              title={u.is_active ? 'Deactivate' : 'Activate'}
              onClick={() => onToggle(u)}
            >
              <Power size={16} className={u.is_active ? 'text-green-600' : 'text-slate-400'} />
            </button>
            <button className="btn-ghost text-red-600" title="Delete" onClick={() => onDelete(u)}>
              <Trash2 size={16} />
            </button>
          </div>
        ) : (
          <span className="text-xs text-slate-400">{u.id === me.id ? 'You' : ''}</span>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Users"
        subtitle="Staff accounts, roles and access"
        actions={
          <>
            <button className="btn-secondary" onClick={onExport}>
              <Download size={16} /> Export CSV
            </button>
            <button className="btn-primary" onClick={() => setEditing({})}>
              <Plus size={16} /> Add user
            </button>
          </>
        }
      />
      <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_200px_160px]">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Search name, username, email, mobile"
        />
        <Select
          value={params.role || ''}
          onChange={(e) => setParams({ role: e.target.value })}
          placeholder="All roles"
          options={roles.map((r) => ({ value: r.code, label: r.name }))}
        />
        <Select
          value={params.is_active ?? ''}
          onChange={(e) => setParams({ is_active: e.target.value })}
          placeholder="All statuses"
          options={[
            { value: 'true', label: 'Active' },
            { value: 'false', label: 'Inactive' },
          ]}
        />
      </div>
      <DataTable
        columns={columns}
        rows={data?.results}
        loading={isLoading}
        ordering={params.ordering}
        onSort={toggleOrdering}
        page={params.page}
        totalPages={data?.total_pages}
        count={data?.count}
        pageSize={params.page_size}
        onPageChange={(p) => setParams({ page: p }, { resetPage: false })}
        emptyText={isFetching ? 'Loading…' : 'No users match your filters.'}
      />
      <UserFormModal
        user={editing}
        roles={roles}
        onClose={() => setEditing(null)}
        onSaved={invalidate}
      />
      <ResetPasswordModal
        user={resetting}
        onClose={() => setResetting(null)}
        onSaved={invalidate}
      />
    </>
  );
}
