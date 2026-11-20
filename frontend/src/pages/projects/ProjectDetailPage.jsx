import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  FilePlus2,
  IndianRupee,
  ListOrdered,
  Pencil,
  Phone,
  Trash2,
  Wallet,
} from 'lucide-react';
import { advancesApi, invoicesApi, paymentsApi, projectsApi } from '@/api/services';
import { api, getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import StatCard from '@/components/ui/StatCard';
import InfoGrid from '@/components/ui/InfoGrid';
import Tabs from '@/components/ui/Tabs';
import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import ProgressBar from '@/components/ui/ProgressBar';
import { Select } from '@/components/ui/Field';
import { formatDate, formatDateTime, formatINR, formatQty } from '@/utils/format';
import { INVOICE_STATUS, PROJECT_STATUS, STAGE_STATUS } from '@/utils/status';
import ProjectFormModal from './ProjectFormModal';
import { IssueMaterialModal, ProgressForm, StagesModal } from './ProjectModals';
import PaymentModal from '../payments/PaymentModal';
import AdvanceModal from '../advances/AdvanceModal';
import { ExpenseList } from '@/pages/expenses/ExpensesPage';

const STATUSES = [
  ['PLANNED', 'Planned'],
  ['IN_PROGRESS', 'In Progress'],
  ['ON_HOLD', 'On Hold'],
  ['COMPLETED', 'Completed'],
];

export default function ProjectDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { hasRole } = useAuth();
  const isAdmin = hasRole('ADMIN');
  const canMoney = hasRole('ADMIN', 'ACCOUNTANT');
  const canSite = hasRole('ADMIN', 'SITE_ENGINEER');
  const [tab, setTab] = useState(canMoney ? 'stages' : 'material');
  const [modal, setModal] = useState(null);
  const [payStage, setPayStage] = useState(null);

  const { data: p, isLoading } = useQuery({
    queryKey: ['projects', id],
    queryFn: () => projectsApi.get(id),
  });
  const { data: summary } = useQuery({
    queryKey: ['projects', id, 'summary'],
    queryFn: () => projectsApi.detail(id, 'summary'),
    enabled: canMoney,
  });
  const { data: mat } = useQuery({
    queryKey: ['projects', id, 'materials'],
    queryFn: () => projectsApi.detail(id, 'materials'),
  });
  const { data: notes = [] } = useQuery({
    queryKey: ['projects', id, 'progress'],
    queryFn: () => projectsApi.detail(id, 'progress'),
  });
  const { data: invoices } = useQuery({
    queryKey: ['invoices', { project: id }],
    queryFn: () => invoicesApi.list({ project: id, page_size: 100 }),
    enabled: canMoney,
  });
  const { data: payments } = useQuery({
    queryKey: ['payments', { project: id }],
    queryFn: () => paymentsApi.list({ project: id, page_size: 100 }),
    enabled: canMoney,
  });
  const { data: advances } = useQuery({
    queryKey: ['advances', { project: id }],
    queryFn: () => advancesApi.list({ project: id, page_size: 100 }),
    enabled: canMoney,
  });
  const refresh = () =>
    ['projects', 'invoices', 'payments', 'advances', 'materials', 'customers'].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );

  if (isLoading || !p) return <div className="card h-64 animate-pulse" />;

  const run = async (fn, ok) => {
    try {
      const r = await fn();
      if (ok) toast.success(ok);
      refresh();
      return r;
    } catch (e) {
      toast.error(getErrorMessage(e));
      return null;
    }
  };
  const invoiceStage = async (s) => {
    if (
      !(await confirm({
        title: `Invoice "${s.name}"?`,
        message: `A GST invoice for ${formatINR(s.amount)} (incl. 18% GST) is created. Any unused advance for this project is adjusted automatically.`,
        confirmText: 'Create invoice',
      }))
    )
      return;
    const created = await run(
      () => api.post('/invoices/from-stage/', { payment_stage: s.id }).then((r) => r.data),
      'Invoice created',
    );
    if (created) navigate(`/invoices/${created.id}`);
  };
  const setStatus = (status) =>
    run(() => projectsApi.action(p.id, 'status', { status }), 'Status updated');
  const undoIssue = async (e) => {
    if (
      await confirm({
        title: 'Remove this entry?',
        message: 'The opposite stock movement is recorded so stock is corrected.',
        confirmText: 'Remove',
        danger: true,
      })
    ) {
      run(() => api.delete(`/projects/${p.id}/materials/${e.id}/`), 'Entry removed');
    }
  };

  const tabs = [
    ...(canMoney
      ? [{ id: 'stages', label: 'Payment stages', count: p.payment_stages.length }]
      : []),
    { id: 'material', label: 'Site material', count: mat?.entries.length },
    { id: 'progress', label: 'Progress', count: notes.length },
    ...(canMoney || canSite ? [{ id: 'expenses', label: 'Expenses' }] : []),
    ...(canMoney
      ? [
          {
            id: 'billing',
            label: 'Invoices & payments',
            count: (invoices?.count || 0) + (payments?.count || 0) + (advances?.count || 0),
          },
        ]
      : []),
  ];

  return (
    <>
      <BackLink to="/projects">All projects</BackLink>
      <PageHeader
        title={p.name}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            {p.code} ·{' '}
            <Link to={`/customers/${p.customer}`} className="hover:underline">
              {p.customer_name}
            </Link>{' '}
            <Badge color={PROJECT_STATUS[p.status]}>{p.status_display}</Badge>
          </span>
        }
        actions={
          <>
            <a href={`tel:${p.customer_detail.phone}`} className="btn-secondary">
              <Phone size={16} /> Call customer
            </a>
            {canSite && p.status !== 'CANCELLED' && (
              <Select
                className="w-auto"
                value={p.status}
                onChange={(e) => setStatus(e.target.value)}
                options={STATUSES.map(([value, label]) => ({ value, label }))}
                aria-label="Project status"
              />
            )}
            {isAdmin && (
              <button className="btn-secondary" onClick={() => setModal('edit')}>
                <Pencil size={16} /> Edit
              </button>
            )}
          </>
        }
      />

      {canMoney && summary && (
        <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Contract value"
            value={formatINR(summary.contract_value)}
            hint={`Unbilled ${formatINR(summary.unbilled)}`}
          />
          <StatCard
            label="Billed"
            value={formatINR(summary.billed)}
            hint={`Outstanding ${formatINR(summary.outstanding)}`}
          />
          <StatCard
            label="Received"
            value={formatINR(summary.received)}
            hint={
              Number(summary.advance_unused)
                ? `Unused advance ${formatINR(summary.advance_unused)}`
                : undefined
            }
          />
          <StatCard
            label="Cost so far"
            value={formatINR(summary.total_cost)}
            hint={`Material ${formatINR(summary.material_cost)} · Expenses ${formatINR(summary.expenses)}${Number(summary.direct_purchases) ? ` · Purchases ${formatINR(summary.direct_purchases)}` : ''}`}
          />
        </div>
      )}
      <div className="mb-4 grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="card">
          <InfoGrid
            cols="sm:grid-cols-2 lg:grid-cols-3"
            items={[
              [
                'Site',
                `${p.site_address}${p.site_city ? `, ${p.site_city}` : ''} ${p.site_pincode || ''}`,
              ],
              ['Engineer', p.engineer_name || 'Not assigned'],
              ['Type', p.project_type_display],
              ['Start', formatDate(p.start_date)],
              ['Expected end', formatDate(p.expected_end_date)],
              [
                'Quotation',
                p.quotation && (
                  <Link
                    className="text-brand-700 hover:underline"
                    to={`/quotations/${p.quotation}`}
                  >
                    {p.quotation_number}
                  </Link>
                ),
              ],
            ]}
          />
          {p.description && (
            <p className="mt-3 whitespace-pre-line text-sm text-slate-600 dark:text-slate-300">
              {p.description}
            </p>
          )}
        </div>
        <div className="card">
          <p className="mb-1 text-sm text-slate-500">Work progress</p>
          <ProgressBar value={p.progress_percent} wide />
          {canMoney && summary && (
            <div className="mt-3 border-t border-slate-100 pt-3 text-sm dark:border-slate-700">
              <p className="text-slate-500">Expected profit</p>
              <p
                className={`text-lg font-semibold ${Number(summary.expected_profit) < 0 ? 'text-red-600' : 'text-green-700'}`}
              >
                {formatINR(summary.expected_profit)}
              </p>
              <p className="text-xs text-slate-500">Contract − cost so far</p>
            </div>
          )}
        </div>
      </div>

      <Tabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === 'stages' && (
        <div className="space-y-3">
          <div className="flex flex-wrap justify-end gap-2">
            <button className="btn-secondary" onClick={() => setModal('advance')}>
              <Wallet size={16} /> Record advance
            </button>
            {isAdmin && (
              <button className="btn-secondary" onClick={() => setModal('stages')}>
                <ListOrdered size={16} /> Edit stages
              </button>
            )}
          </div>
          <DataTable
            rows={p.payment_stages}
            emptyText="No payment stages. Set the contract value and add stages."
            columns={[
              {
                key: 'n',
                header: 'Stage',
                render: (s) => (
                  <div>
                    <p className="font-medium">{s.name}</p>
                    <p className="text-xs text-slate-500">
                      {Number(s.percentage)}%{s.due_date ? ` · due ${formatDate(s.due_date)}` : ''}
                    </p>
                  </div>
                ),
              },
              {
                key: 'a',
                header: 'Amount',
                className: 'text-right',
                render: (s) => formatINR(s.amount),
              },
              {
                key: 'r',
                header: 'Received',
                className: 'text-right',
                render: (s) => formatINR(s.amount_received),
              },
              {
                key: 's',
                header: 'Status',
                render: (s) => <Badge color={STAGE_STATUS[s.status]}>{s.status_display}</Badge>,
              },
              {
                key: 'i',
                header: 'Invoice',
                render: (s) =>
                  s.invoices.map((i) => (
                    <Link
                      key={i.id}
                      to={`/invoices/${i.id}`}
                      className="block text-brand-700 hover:underline"
                    >
                      {i.number}
                    </Link>
                  )),
              },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (s) =>
                  s.status !== 'PAID' && (
                    <div className="flex justify-end gap-1">
                      {s.invoices.length === 0 && Number(s.amount_received) === 0 && (
                        <button
                          className="btn-secondary px-2 py-1 text-xs"
                          onClick={() => invoiceStage(s)}
                        >
                          <FilePlus2 size={14} /> Invoice
                        </button>
                      )}
                      <button
                        className="btn-secondary px-2 py-1 text-xs"
                        onClick={() => setPayStage(s)}
                      >
                        <IndianRupee size={14} /> Payment
                      </button>
                    </div>
                  ),
              },
            ]}
          />
        </div>
      )}

      {tab === 'material' && (
        <div className="space-y-3">
          {canSite && p.status !== 'CANCELLED' && (
            <div className="flex flex-wrap justify-end gap-2">
              <button className="btn-secondary" onClick={() => setModal('return')}>
                <ArrowDownToLine size={16} /> Return to store
              </button>
              <button className="btn-primary" onClick={() => setModal('issue')}>
                <ArrowUpFromLine size={16} /> Issue material
              </button>
            </div>
          )}
          <DataTable
            rows={mat?.summary}
            rowKey="material"
            loading={!mat}
            emptyText="No material issued to this site yet."
            columns={[
              {
                key: 'n',
                header: 'Material at site',
                render: (r) => <span className="font-medium">{r.name}</span>,
              },
              {
                key: 'i',
                header: 'Issued',
                className: 'text-right',
                render: (r) => `${formatQty(r.issued)} ${r.unit}`,
              },
              {
                key: 'rt',
                header: 'Returned',
                className: 'text-right',
                render: (r) => formatQty(r.returned),
              },
              {
                key: 'net',
                header: 'Used / at site',
                className: 'text-right',
                render: (r) => (
                  <b>
                    {formatQty(r.net)} {r.unit}
                  </b>
                ),
              },
              ...(canMoney
                ? [
                    {
                      key: 'c',
                      header: 'Cost',
                      className: 'text-right',
                      render: (r) => formatINR(r.cost),
                    },
                  ]
                : []),
            ]}
          />
          <h3 className="pt-2 text-sm font-semibold text-slate-500">All entries</h3>
          <DataTable
            rows={mat?.entries}
            loading={!mat}
            emptyText="—"
            columns={[
              { key: 'd', header: 'Date', render: (e) => formatDate(e.issue_date) },
              {
                key: 'm',
                header: 'Material',
                render: (e) => (
                  <span>
                    {e.is_return && <Badge color="green">Return</Badge>} {e.material_name}
                  </span>
                ),
              },
              {
                key: 'q',
                header: 'Qty',
                className: 'text-right',
                render: (e) => (
                  <span className={e.is_return ? 'text-green-700' : ''}>
                    {e.is_return ? '−' : ''}
                    {formatQty(e.quantity)} {e.unit}
                  </span>
                ),
              },
              {
                key: 'w',
                header: 'Details',
                mobileHidden: true,
                render: (e) => (
                  <span className="text-xs text-slate-500">
                    {[e.notes, e.received_by_name, e.vehicle_number, e.issued_by_name]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                ),
              },
              ...(canMoney
                ? [
                    {
                      key: 'a',
                      header: 'Cost',
                      className: 'text-right',
                      render: (e) => formatINR(e.amount),
                    },
                  ]
                : []),
              ...(isAdmin
                ? [
                    {
                      key: 'x',
                      header: '',
                      className: 'text-right',
                      render: (e) => (
                        <button
                          className="btn-ghost px-2 text-red-600"
                          title="Remove wrong entry"
                          onClick={() => undoIssue(e)}
                        >
                          <Trash2 size={15} />
                        </button>
                      ),
                    },
                  ]
                : []),
            ]}
          />
        </div>
      )}

      {tab === 'progress' && (
        <div className="space-y-4">
          {canSite && <ProgressForm project={p} onSaved={refresh} />}
          {notes.length === 0 && <p className="text-sm text-slate-500">No updates yet.</p>}
          <ol className="space-y-3">
            {notes.map((n) => (
              <li key={n.id} className="card">
                <div className="mb-1 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span>
                    <b className="text-slate-700 dark:text-slate-200">{formatDate(n.date)}</b> ·{' '}
                    {n.created_by_name}
                    {n.workers_on_site ? ` · ${n.workers_on_site} workers` : ''}
                  </span>
                  {n.progress_percent !== null && (
                    <Badge color="orange">{Number(n.progress_percent)}% done</Badge>
                  )}
                </div>
                <p className="whitespace-pre-line text-sm">{n.note}</p>
                {n.photos.length > 0 && (
                  <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-6">
                    {n.photos.map((ph) => (
                      <a key={ph.id} href={ph.image} target="_blank" rel="noreferrer">
                        <img
                          src={ph.image}
                          alt={ph.caption || 'Site photo'}
                          className="aspect-square w-full rounded-lg object-cover"
                          loading="lazy"
                        />
                      </a>
                    ))}
                  </div>
                )}
                <p className="mt-1 text-[11px] text-slate-400">{formatDateTime(n.created_at)}</p>
              </li>
            ))}
          </ol>
        </div>
      )}

      {tab === 'expenses' && <ExpenseList projectId={p.id} compact />}

      {tab === 'billing' && (
        <div className="space-y-4">
          <div className="flex justify-end gap-2">
            <Link
              to={`/invoices/new?customer=${p.customer}&project=${p.id}`}
              className="btn-secondary"
            >
              <FilePlus2 size={16} /> New invoice
            </Link>
          </div>
          <DataTable
            rows={invoices?.results}
            loading={!invoices}
            onRowClick={(i) => navigate(`/invoices/${i.id}`)}
            emptyText="No invoices yet."
            columns={[
              {
                key: 'n',
                header: 'Invoice',
                render: (i) => <span className="font-medium">{i.number}</span>,
              },
              { key: 'd', header: 'Date', render: (i) => formatDate(i.invoice_date) },
              {
                key: 's',
                header: 'Status',
                render: (i) => <Badge color={INVOICE_STATUS[i.status]}>{i.status_display}</Badge>,
              },
              {
                key: 't',
                header: 'Total',
                className: 'text-right',
                render: (i) => formatINR(i.grand_total),
              },
              {
                key: 'b',
                header: 'Balance',
                className: 'text-right',
                render: (i) => formatINR(i.balance_due),
              },
            ]}
          />
          <DataTable
            rows={[
              ...(advances?.results || []).map((a) => ({
                ...a,
                _kind: 'Advance',
                key: `a${a.id}`,
              })),
              ...(payments?.results || []).map((x) => ({
                ...x,
                _kind: 'Payment',
                key: `p${x.id}`,
              })),
            ].sort((a, b) => (a.date < b.date ? 1 : -1))}
            rowKey="key"
            loading={!payments || !advances}
            emptyText="No money received yet."
            onRowClick={(r) => r._kind === 'Advance' && navigate(`/advances/${r.id}`)}
            columns={[
              {
                key: 'r',
                header: 'Receipt',
                render: (r) => (
                  <span>
                    <Badge color={r._kind === 'Advance' ? 'blue' : 'green'}>{r._kind}</Badge>{' '}
                    {r.receipt_number}
                  </span>
                ),
              },
              { key: 'd', header: 'Date', render: (r) => formatDate(r.date) },
              {
                key: 'f',
                header: 'For',
                render: (r) =>
                  r.invoice_number ||
                  r.stage_name ||
                  (r._kind === 'Advance' ? `Unused ${formatINR(r.balance)}` : ''),
              },
              { key: 'm', header: 'Mode', render: (r) => r.mode_display },
              {
                key: 'a',
                header: 'Amount',
                className: 'text-right',
                render: (r) => formatINR(r.amount),
              },
            ]}
          />
        </div>
      )}

      <ProjectFormModal
        project={modal === 'edit' ? p : null}
        onClose={() => setModal(null)}
        onSaved={refresh}
      />
      {modal === 'stages' && (
        <StagesModal project={p} open onClose={() => setModal(null)} onSaved={refresh} />
      )}
      <IssueMaterialModal
        project={p}
        open={modal === 'issue' || modal === 'return'}
        isReturn={modal === 'return'}
        siteStock={mat?.summary || []}
        onClose={() => setModal(null)}
        onSaved={refresh}
      />
      <PaymentModal
        open={!!payStage}
        onClose={() => setPayStage(null)}
        customerId={p.customer}
        invoiceId={payStage?.invoices.find((i) => i.status !== 'PAID')?.id}
        stageId={payStage && payStage.invoices.length === 0 ? payStage.id : undefined}
        onSaved={refresh}
      />
      <AdvanceModal
        open={modal === 'advance'}
        onClose={() => setModal(null)}
        customerId={p.customer}
        projectId={p.id}
        onSaved={refresh}
      />
    </>
  );
}
