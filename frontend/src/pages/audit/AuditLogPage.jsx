import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { auditApi } from '@/api/services';
import { useListParams } from '@/hooks/useListParams';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import { Input, Select } from '@/components/ui/Field';
import { exportCsv } from '@/utils/exportCsv';
import { formatDateTime } from '@/utils/format';

const ACTIONS = [
  ['CREATE', 'Created', 'green'],
  ['UPDATE', 'Updated', 'blue'],
  ['DELETE', 'Deleted', 'red'],
  ['RESTORE', 'Restored', 'green'],
  ['STATUS', 'Status changed', 'blue'],
  ['LOGIN', 'Logged in', 'gray'],
  ['LOGIN_FAIL', 'Login failed', 'amber'],
  ['LOGOUT', 'Logged out', 'gray'],
  ['PASSWORD', 'Password', 'purple'],
  ['EXPORT', 'Exported', 'gray'],
];
const ACTION_COLOR = Object.fromEntries(ACTIONS.map(([v, , c]) => [v, c]));
const MODELS = [
  ['accounts.User', 'Users'],
  ['core.CompanySettings', 'Company settings'],
  ['core.DocumentSequence', 'Number series'],
  ['customers.Customer', 'Customers'],
  ['materials.Material', 'Materials'],
  ['quotations.Quotation', 'Quotations'],
  ['projects.Project', 'Projects'],
  ['invoices.Invoice', 'Invoices'],
  ['payments.Payment', 'Payments'],
  ['payments.AdvancePayment', 'Advances'],
  ['expenses.Expense', 'Expenses'],
];
const modelLabel = (m) => MODELS.find(([v]) => v === m)?.[1] || m;

export default function AuditLogPage() {
  const { params, setParams, toggleOrdering } = useListParams({ ordering: '-timestamp' });
  const [detail, setDetail] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', params],
    queryFn: () => auditApi.list(params),
    placeholderData: keepPreviousData,
  });

  const onExport = async () => {
    const all = await auditApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-audit-log',
      [
        { header: 'Date & time', value: (r) => formatDateTime(r.timestamp) },
        { header: 'User', value: (r) => r.user_name },
        { header: 'Action', value: (r) => r.action_display },
        { header: 'Module', value: (r) => modelLabel(r.model_name) },
        { header: 'Record', value: (r) => r.object_repr },
        { header: 'IP', value: (r) => r.ip_address },
        { header: 'Changes', value: (r) => JSON.stringify(r.changes) },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'timestamp',
      header: 'When',
      sortField: 'timestamp',
      render: (r) => <span className="whitespace-nowrap">{formatDateTime(r.timestamp)}</span>,
    },
    { key: 'user', header: 'User', render: (r) => r.user_name },
    {
      key: 'action',
      header: 'Action',
      sortField: 'action',
      render: (r) => <Badge color={ACTION_COLOR[r.action]}>{r.action_display}</Badge>,
    },
    { key: 'model', header: 'Module', render: (r) => modelLabel(r.model_name) },
    {
      key: 'object',
      header: 'Record',
      render: (r) => (
        <span className="line-clamp-1">
          {r.object_repr || (r.object_id ? `#${r.object_id}` : '—')}
        </span>
      ),
    },
    {
      key: 'ip',
      header: 'IP',
      mobileHidden: true,
      render: (r) => <span className="text-xs text-slate-500">{r.ip_address || ''}</span>,
    },
  ];

  return (
    <>
      <PageHeader
        title="Audit log"
        subtitle="Who created, changed or deleted what, and when"
        actions={
          <button className="btn-secondary" onClick={onExport}>
            <Download size={16} /> Export CSV
          </button>
        }
      />
      <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-[1fr_160px_180px_150px_150px]">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Search record or user"
        />
        <Select
          value={params.action || ''}
          onChange={(e) => setParams({ action: e.target.value })}
          placeholder="All actions"
          options={ACTIONS.map(([value, label]) => ({ value, label }))}
        />
        <Select
          value={params.model_name || ''}
          onChange={(e) => setParams({ model_name: e.target.value })}
          placeholder="All modules"
          options={MODELS.map(([value, label]) => ({ value, label }))}
        />
        <Input
          type="date"
          value={params.date_from || ''}
          onChange={(e) => setParams({ date_from: e.target.value })}
          title="From date"
        />
        <Input
          type="date"
          value={params.date_to || ''}
          onChange={(e) => setParams({ date_to: e.target.value })}
          title="To date"
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
        onRowClick={setDetail}
      />
      <Modal open={!!detail} onClose={() => setDetail(null)} title="Audit entry" size="lg">
        {detail && (
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="text-slate-500">When</p>
                <p>{formatDateTime(detail.timestamp)}</p>
              </div>
              <div>
                <p className="text-slate-500">User</p>
                <p>{detail.user_name}</p>
              </div>
              <div>
                <p className="text-slate-500">Action</p>
                <Badge color={ACTION_COLOR[detail.action]}>{detail.action_display}</Badge>
              </div>
              <div>
                <p className="text-slate-500">Module / record</p>
                <p>
                  {modelLabel(detail.model_name)} · {detail.object_repr || detail.object_id}
                </p>
              </div>
            </div>
            {Object.keys(detail.changes || {}).length > 0 && (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-900/40">
                  <tr>
                    <th className="p-2">Field</th>
                    <th className="p-2">Before</th>
                    <th className="p-2">After</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {Object.entries(detail.changes).map(([field, [before, after]]) => (
                    <tr key={field}>
                      <td className="p-2 font-medium">{field.replace(/_/g, ' ')}</td>
                      <td className="p-2 text-red-700 dark:text-red-300">{before ?? '—'}</td>
                      <td className="p-2 text-green-700 dark:text-green-300">{after ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}
