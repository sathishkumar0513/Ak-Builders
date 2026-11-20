import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  FileText,
  HardHat,
  IndianRupee,
  PackageX,
  Receipt,
  RefreshCw,
  Users,
  Wallet2,
  XCircle,
} from 'lucide-react';
import { dashboardApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import Badge from '@/components/ui/Badge';
import ProgressBar from '@/components/ui/ProgressBar';
import { BarChart, DonutChart, HBarList } from '@/components/charts/Charts';
import { CHART_COLORS } from '@/utils/chart';
import { formatDate, formatINR, formatQty } from '@/utils/format';
import { PROJECT_STATUS } from '@/utils/status';

function Card({ label, value, hint, icon: Icon, to, tone = 'brand', loading }) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600 dark:bg-brand-900/30',
    red: 'bg-red-50 text-red-600 dark:bg-red-900/30',
    green: 'bg-green-50 text-green-600 dark:bg-green-900/30',
    blue: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30',
  };
  const body = (
    <div className="card flex h-full items-start justify-between gap-3 transition hover:border-slate-300 dark:hover:border-slate-600">
      <div className="min-w-0">
        <p className="text-sm text-slate-500">{label}</p>
        {loading ? (
          <div className="mt-2 h-7 w-24 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
        ) : (
          <p className="mt-1 truncate text-2xl font-semibold">{value}</p>
        )}
        {hint && !loading && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      </div>
      {Icon && (
        <div className={`shrink-0 rounded-lg p-2 ${tones[tone]}`}>
          <Icon size={20} />
        </div>
      )}
    </div>
  );
  return to ? (
    <Link to={to} className="block">
      {body}
    </Link>
  ) : (
    body
  );
}

function Panel({ title, action, children, className = '' }) {
  return (
    <section className={`card min-w-0 ${className}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

const Empty = ({ children }) => (
  <p className="py-4 text-center text-sm text-slate-500">{children}</p>
);

export default function Dashboard() {
  const { user, hasRole } = useAuth();
  const finance = hasRole('ADMIN', 'ACCOUNTANT');
  const sales = hasRole('ADMIN', 'ACCOUNTANT', 'SALES');
  const engineer = user?.role_code === 'SITE_ENGINEER';
  const {
    data: d,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.get,
    refetchInterval: 5 * 60_000,
  });
  const c = d?.cards || {};

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Welcome, {user?.first_name || user?.username}</h1>
          <p className="text-sm text-slate-500">
            {user?.role_name} · {formatDate(new Date())}
            {d ? ` · FY ${d.financial_year}` : ''}
          </p>
        </div>
        <button className="btn-ghost text-sm" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {isError && (
        <div className="card flex items-center gap-3 text-sm text-red-700">
          <XCircle size={20} /> Couldn&apos;t load the dashboard: {getErrorMessage(error)}
        </div>
      )}

      {/* ---- cards ---- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {finance && (
          <>
            <Card
              label="Received this year"
              value={formatINR(c.received_fy)}
              hint={`This month ${formatINR(c.received_month)}`}
              icon={IndianRupee}
              tone="green"
              to="/reports/payments"
              loading={isLoading}
            />
            <Card
              label="Total outstanding"
              value={formatINR(c.outstanding)}
              hint={
                Number(c.overdue) > 0
                  ? `${formatINR(c.overdue)} overdue on ${c.overdue_count} invoice${c.overdue_count === 1 ? '' : 's'}`
                  : 'Nothing overdue'
              }
              icon={AlertTriangle}
              tone={Number(c.overdue) > 0 ? 'red' : 'brand'}
              to="/reports/outstanding"
              loading={isLoading}
            />
          </>
        )}
        {sales && (
          <Card
            label="Total customers"
            value={c.total_customers ?? '—'}
            icon={Users}
            tone="blue"
            to="/customers"
            loading={isLoading}
          />
        )}
        <Card
          label={engineer ? 'My active projects' : 'Active projects'}
          value={c.active_projects ?? '—'}
          hint="Planned, in progress or on hold"
          icon={HardHat}
          to="/projects"
          loading={isLoading}
        />
        {sales && (
          <Card
            label="Pending quotations"
            value={c.pending_quotations ?? '—'}
            hint="Draft or sent, waiting for the customer"
            icon={FileText}
            to="/quotations?status=SENT"
            loading={isLoading}
          />
        )}
        <Card
          label="Low-stock items"
          value={c.low_stock ?? '—'}
          hint="At or below reorder level"
          icon={PackageX}
          tone={c.low_stock ? 'red' : 'green'}
          to="/materials?low_stock=true"
          loading={isLoading}
        />
        {finance && (
          <>
            <Card
              label="Billed this year"
              value={formatINR(c.billed_fy)}
              icon={Receipt}
              to="/invoices"
              loading={isLoading}
            />
            <Card
              label="Expenses this month"
              value={formatINR(c.expenses_month)}
              hint={
                c.pending_expense_approvals
                  ? `${c.pending_expense_approvals} waiting for approval`
                  : 'All approved'
              }
              icon={Wallet2}
              tone={c.pending_expense_approvals ? 'red' : 'brand'}
              to={c.pending_expense_approvals ? '/expenses?approved=false' : '/expenses'}
              loading={isLoading}
            />
          </>
        )}
        {engineer && (
          <Card
            label="My expenses awaiting approval"
            value={c.my_pending_expenses ?? '—'}
            icon={Wallet2}
            to="/expenses?approved=false"
            loading={isLoading}
          />
        )}
      </div>

      {/* ---- charts (finance) ---- */}
      {finance && d?.monthly && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Panel title="Monthly revenue" className="lg:col-span-2">
            <BarChart
              data={d.monthly.map((m) => ({ ...m, label: m.month }))}
              series={[
                { key: 'billed', label: 'Billed', color: CHART_COLORS[0] },
                { key: 'received', label: 'Received', color: CHART_COLORS[1] },
                { key: 'expenses', label: 'Expenses', color: '#94a3b8' },
              ]}
            />
          </Panel>
          <Panel title="Payment modes (this FY)">
            {d.payment_modes.length ? (
              <DonutChart
                items={d.payment_modes.map((m) => ({ label: m.label, value: Number(m.amount) }))}
                centerLabel="Received"
              />
            ) : (
              <Empty>No receipts yet this year.</Empty>
            )}
          </Panel>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {finance && d?.top_customers && (
          <Panel
            title="Top customers (this FY)"
            action={
              <Link
                to="/reports/customer-outstanding"
                className="text-sm text-brand-700 hover:underline"
              >
                All
              </Link>
            }
          >
            {d.top_customers.length ? (
              <HBarList
                items={d.top_customers.map((t) => ({
                  label: t.name,
                  value: Number(t.billed),
                  sub: Number(t.due) > 0 ? `${formatINR(t.due)} due` : 'Fully paid',
                }))}
              />
            ) : (
              <Empty>No invoices yet this year.</Empty>
            )}
          </Panel>
        )}

        <Panel title={engineer ? 'My projects by status' : 'Projects by status'}>
          {d?.project_status?.length ? (
            <HBarList
              color={CHART_COLORS[2]}
              format={(v) => v}
              items={d.project_status.map((s) => ({ label: s.label, value: s.count }))}
            />
          ) : (
            <Empty>{isLoading ? 'Loading…' : 'No projects yet.'}</Empty>
          )}
        </Panel>

        {engineer && (
          <Panel title="My active sites" className="lg:col-span-2">
            {d?.my_projects?.length ? (
              <ul className="divide-y divide-slate-100 dark:divide-slate-700">
                {d.my_projects.map((p) => (
                  <li key={p.id}>
                    <Link
                      to={`/projects/${p.id}`}
                      className="flex items-center justify-between gap-3 py-2.5 hover:text-brand-700"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium">{p.name}</p>
                        <p className="text-xs text-slate-500">
                          {p.code}
                          {p.site_city ? ` · ${p.site_city}` : ''}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-3">
                        <Badge color={PROJECT_STATUS[p.status]}>{p.status_display}</Badge>
                        <ProgressBar value={p.progress} />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>No active projects assigned to you.</Empty>
            )}
          </Panel>
        )}

        <Panel
          title="Low stock"
          action={
            <Link to="/materials?low_stock=true" className="text-sm text-brand-700 hover:underline">
              All
            </Link>
          }
        >
          {d?.low_stock?.length ? (
            <ul className="space-y-2 text-sm">
              {d.low_stock.map((m) => (
                <li key={m.id} className="flex justify-between gap-2">
                  <Link to={`/materials/${m.id}`} className="truncate hover:text-brand-700">
                    {m.name}
                  </Link>
                  <span className="shrink-0 text-red-600">
                    {formatQty(m.stock)} / {formatQty(m.reorder_level)} {m.unit}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>{isLoading ? 'Loading…' : 'Stock levels are fine.'}</Empty>
          )}
        </Panel>
      </div>

      {(finance || sales) && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {finance && d?.overdue_invoices && (
            <Panel
              title="Overdue invoices"
              action={
                <Link to="/reports/outstanding" className="text-sm text-brand-700 hover:underline">
                  Ageing report
                </Link>
              }
            >
              {d.overdue_invoices.length ? (
                <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
                  {d.overdue_invoices.map((i) => (
                    <li key={i.id}>
                      <Link
                        to={`/invoices/${i.id}`}
                        className="flex items-center justify-between gap-3 py-2 hover:text-brand-700"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-medium">{i.customer}</p>
                          <p className="text-xs text-slate-500">
                            {i.number} · due {formatDate(i.due_date)}
                          </p>
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="font-medium text-red-600">{formatINR(i.balance_due)}</p>
                          <p className="text-xs text-slate-500">{i.days} days late</p>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>No overdue invoices. 🎉</Empty>
              )}
            </Panel>
          )}
          {finance && d?.recent_receipts && (
            <Panel
              title="Recent receipts"
              action={
                <Link to="/payments" className="text-sm text-brand-700 hover:underline">
                  All
                </Link>
              }
            >
              {d.recent_receipts.length ? (
                <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
                  {d.recent_receipts.map((r) => (
                    <li key={`${r.kind}-${r.id}`}>
                      <Link
                        to={r.kind === 'advance' ? `/advances/${r.id}` : '/payments'}
                        className="flex items-center justify-between gap-3 py-2 hover:text-brand-700"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-medium">{r.customer}</p>
                          <p className="text-xs text-slate-500">
                            {r.number} · {formatDate(r.date)} · {r.mode}
                            {r.kind === 'advance' ? ' · advance' : ''}
                          </p>
                        </div>
                        <p className="shrink-0 font-medium text-green-700">{formatINR(r.amount)}</p>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>No receipts yet.</Empty>
              )}
            </Panel>
          )}
          {sales && d?.expiring_quotations && (
            <Panel title="Quotations expiring this week">
              {d.expiring_quotations.length ? (
                <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
                  {d.expiring_quotations.map((q) => (
                    <li key={q.id}>
                      <Link
                        to={`/quotations/${q.id}`}
                        className="flex items-center justify-between gap-3 py-2 hover:text-brand-700"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-medium">{q.customer}</p>
                          <p className="text-xs text-slate-500">
                            {q.number} · valid till {formatDate(q.valid_until)}
                          </p>
                        </div>
                        <p className="shrink-0 font-medium">{formatINR(q.grand_total)}</p>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>No sent quotations expire in the next 7 days.</Empty>
              )}
            </Panel>
          )}
        </div>
      )}
    </div>
  );
}
