import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import clsx from 'clsx';
import { Plus } from 'lucide-react';
import { projectsApi, usersApi } from '@/api/services';
import { useAuth } from '@/context/AuthContext';
import { useListParams } from '@/hooks/useListParams';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Select } from '@/components/ui/Field';
import { formatDate, formatINR } from '@/utils/format';
import { PROJECT_STATUS } from '@/utils/status';
import ProjectFormModal from './ProjectFormModal';
import ProgressBar from '@/components/ui/ProgressBar';

const CHIPS = [
  ['', 'All'],
  ['PLANNED', 'Planned'],
  ['IN_PROGRESS', 'In progress'],
  ['ON_HOLD', 'On hold'],
  ['COMPLETED', 'Completed'],
  ['CANCELLED', 'Cancelled'],
];

export default function ProjectsPage() {
  const navigate = useNavigate();
  const { hasRole, user } = useAuth();
  const isEngineer = user?.role_code === 'SITE_ENGINEER';
  const canMoney = hasRole('ADMIN', 'ACCOUNTANT');
  const { params, setParams, toggleOrdering } = useListParams({ ordering: '-created_at' });
  const [editing, setEditing] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ['projects', params],
    queryFn: () => projectsApi.list(params),
    placeholderData: keepPreviousData,
  });
  const { data: engineers = [] } = useQuery({
    queryKey: ['users', 'engineers'],
    queryFn: () => usersApi.lookup({ role: 'SITE_ENGINEER' }),
    enabled: !isEngineer,
  });

  const columns = [
    {
      key: 'code',
      header: 'Project',
      sortField: 'code',
      render: (p) => (
        <div>
          <p className="font-medium">{p.name}</p>
          <p className="text-xs text-slate-500">
            {p.code} · {p.customer_name}
          </p>
        </div>
      ),
    },
    { key: 'site', header: 'Site', mobileHidden: true, render: (p) => p.site_city || '—' },
    {
      key: 'eng',
      header: 'Engineer',
      render: (p) => p.engineer_name || <span className="text-slate-400">—</span>,
    },
    {
      key: 'dates',
      header: 'Start / end',
      sortField: 'start_date',
      render: (p) => (
        <span className="text-xs">
          {formatDate(p.start_date) || '—'} → {formatDate(p.expected_end_date) || '—'}
        </span>
      ),
    },
    {
      key: 'prog',
      header: 'Progress',
      sortField: 'progress_percent',
      render: (p) => <ProgressBar value={p.progress_percent} />,
    },
    {
      key: 'st',
      header: 'Status',
      render: (p) => <Badge color={PROJECT_STATUS[p.status]}>{p.status_display}</Badge>,
    },
    ...(canMoney
      ? [
          {
            key: 'val',
            header: 'Contract',
            sortField: 'contract_value',
            className: 'text-right',
            render: (p) => formatINR(p.contract_value),
          },
        ]
      : []),
  ];

  return (
    <>
      <PageHeader
        title={isEngineer ? 'My sites' : 'Projects & sites'}
        subtitle={data ? `${data.count} projects` : ' '}
        actions={
          hasRole('ADMIN') && (
            <button className="btn-primary" onClick={() => setEditing({})}>
              <Plus size={16} /> New project
            </button>
          )
        }
      />
      <div className="no-scrollbar mb-3 flex gap-1 overflow-x-auto">
        {CHIPS.map(([v, l]) => (
          <button
            key={v}
            onClick={() => setParams({ status: v })}
            className={clsx(
              'whitespace-nowrap rounded-full px-3 py-1 text-sm',
              (params.status || '') === v
                ? 'bg-brand-600 text-white'
                : 'bg-white text-slate-600 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300',
            )}
          >
            {l}
          </button>
        ))}
      </div>
      <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_200px]">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Project, code, customer, site"
        />
        {!isEngineer && (
          <Select
            value={params.assigned_engineer || ''}
            onChange={(e) => setParams({ assigned_engineer: e.target.value })}
            placeholder="All engineers"
            options={engineers.map((u) => ({ value: u.id, label: u.name }))}
          />
        )}
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
        onRowClick={(p) => navigate(`/projects/${p.id}`)}
        emptyText={
          isEngineer
            ? 'No sites are assigned to you yet.'
            : 'No projects yet. Convert an approved quotation or click New project.'
        }
      />
      <ProjectFormModal
        project={editing}
        onClose={() => setEditing(null)}
        onSaved={(p) => navigate(`/projects/${p.id}`)}
      />
    </>
  );
}
