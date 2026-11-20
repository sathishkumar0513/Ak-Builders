import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  FilePlus2,
  IndianRupee,
  Mail,
  MessageCircle,
  Pencil,
  Phone,
  Trash2,
  Wallet,
} from 'lucide-react';
import { customersApi } from '@/api/services';
import { useAuth } from '@/context/AuthContext';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import InfoGrid from '@/components/ui/InfoGrid';
import StatCard from '@/components/ui/StatCard';
import Tabs from '@/components/ui/Tabs';
import Badge from '@/components/ui/Badge';
import { formatDate, formatINR } from '@/utils/format';
import { QUOTATION_STATUS } from '@/utils/status';
import CustomerFormModal from './CustomerFormModal';
import LedgerTab from './LedgerTab';
import PaymentModal from '../payments/PaymentModal';
import AdvanceModal from '../advances/AdvanceModal';

function MiniList({ rows, columns, empty }) {
  if (!rows?.length) return <p className="py-6 text-center text-sm text-slate-500">{empty}</p>;
  return (
    <table className="w-full text-sm">
      <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
        {rows.map((r) => (
          <tr key={r.id}>
            {columns.map((c, i) => (
              <td key={i} className={`py-2 ${c.className || ''}`}>
                {c.render(r)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function CustomerDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { hasRole } = useAuth();
  const [tab, setTab] = useState('quotations');
  const [editing, setEditing] = useState(null);
  const [moneyModal, setMoneyModal] = useState(null);
  const canMoney = hasRole('ADMIN', 'ACCOUNTANT');
  const { data: c, isLoading } = useQuery({
    queryKey: ['customers', id],
    queryFn: () => customersApi.get(id),
  });
  const { data: s } = useQuery({
    queryKey: ['customers', id, 'summary'],
    queryFn: () => customersApi.detail(id, 'summary'),
  });
  const del = useMutation({
    mutationFn: () => customersApi.remove(id),
    onSuccess: () => {
      toast.success('Customer deleted');
      qc.invalidateQueries({ queryKey: ['customers'] });
      navigate('/customers');
    },
  });

  if (isLoading || !c) return <div className="card h-64 animate-pulse" />;
  const outstanding = Number(s?.outstanding || 0);
  const wa = `https://wa.me/91${c.phone}`;

  const onDelete = async () => {
    if (
      await confirm({
        title: 'Delete customer?',
        message: `${c.name} will be hidden from lists. Existing quotations, invoices and payments stay.`,
        confirmText: 'Delete',
        danger: true,
      })
    )
      del.mutate();
  };

  return (
    <>
      <BackLink to="/customers">All customers</BackLink>
      <PageHeader
        title={c.name}
        subtitle={[c.customer_type_display, c.city, c.state_name].filter(Boolean).join(' · ')}
        actions={
          <>
            {canMoney && (
              <button className="btn-secondary" onClick={() => setMoneyModal('pay')}>
                <IndianRupee size={16} /> Payment
              </button>
            )}
            {canMoney && (
              <button className="btn-secondary" onClick={() => setMoneyModal('advance')}>
                <Wallet size={16} /> Advance
              </button>
            )}
            <Link to={`/quotations/new?customer=${c.id}`} className="btn-primary">
              <FilePlus2 size={16} /> New quotation
            </Link>
            <a href={`tel:${c.phone}`} className="btn-secondary">
              <Phone size={16} /> Call
            </a>
            <a href={wa} target="_blank" rel="noreferrer" className="btn-secondary">
              <MessageCircle size={16} /> WhatsApp
            </a>
            {c.email && (
              <a href={`mailto:${c.email}`} className="btn-secondary">
                <Mail size={16} /> Email
              </a>
            )}
            <button className="btn-secondary" onClick={() => setEditing(c)}>
              <Pencil size={16} /> Edit
            </button>
            {hasRole('ADMIN') && (
              <button className="btn-ghost text-red-600" onClick={onDelete} title="Delete">
                <Trash2 size={16} />
              </button>
            )}
          </>
        }
      />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Outstanding"
          value={
            <span className={outstanding > 0 ? 'text-red-600' : ''}>
              {formatINR(Math.max(outstanding, 0))}
            </span>
          }
        />
        <StatCard label="Advance balance" value={formatINR(s?.advance_balance || 0)} />
        <StatCard label="Total billed" value={formatINR(s?.total_billed || 0)} />
        <StatCard label="Total received" value={formatINR(s?.total_received || 0)} />
      </div>
      <div className="card mb-4">
        <InfoGrid
          items={[
            ['Mobile', c.phone],
            ['Alternate', c.alternate_phone],
            ['Email', c.email],
            ['Contact person', c.contact_person],
            ['GSTIN', c.gstin],
            ['Pincode', c.pincode],
            ['Address', c.address],
            ['Notes', c.notes],
          ]}
        />
      </div>
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: 'quotations', label: 'Quotations', count: s?.counts.quotations },
          { id: 'projects', label: 'Projects', count: s?.counts.projects },
          { id: 'payments', label: 'Payments', count: s?.counts.payments },
          ...(canMoney ? [{ id: 'ledger', label: 'Ledger' }] : []),
        ]}
      />
      {tab === 'ledger' && <LedgerTab customer={c} />}
      <div className={tab === 'ledger' ? 'hidden' : 'card'}>
        {tab === 'quotations' && (
          <MiniList
            rows={s?.recent_quotations}
            empty="No quotations yet."
            columns={[
              {
                render: (q) => (
                  <Link
                    to={`/quotations/${q.id}`}
                    className="font-medium text-brand-700 hover:underline"
                  >
                    {q.number} <span className="text-xs text-slate-500">Rev {q.revision}</span>
                  </Link>
                ),
              },
              { render: (q) => formatDate(q.quotation_date) },
              {
                render: (q) => (
                  <Badge color={QUOTATION_STATUS[q.status]}>{q.status.toLowerCase()}</Badge>
                ),
              },
              { className: 'text-right', render: (q) => formatINR(q.grand_total) },
            ]}
          />
        )}
        {tab === 'projects' && (
          <MiniList
            rows={s?.recent_projects}
            empty="No projects yet."
            columns={[
              {
                render: (p) => (
                  <Link
                    to={`/projects/${p.id}`}
                    className="font-medium text-brand-700 hover:underline"
                  >
                    {p.code}
                  </Link>
                ),
              },
              { render: (p) => p.name },
              { render: (p) => <Badge>{p.status}</Badge> },
            ]}
          />
        )}
        {tab === 'payments' && (
          <MiniList
            rows={s?.recent_payments}
            empty="No payments yet."
            columns={[
              { render: (p) => p.receipt_number },
              { render: (p) => formatDate(p.date) },
              { render: (p) => p.mode },
              { className: 'text-right', render: (p) => formatINR(p.amount) },
            ]}
          />
        )}
      </div>
      <p className="mt-3 text-xs text-slate-400">
        <Link to="/customers" className="hover:underline">
          Customers
        </Link>{' '}
        · Created {formatDate(c.created_at)}
      </p>
      <PaymentModal
        open={moneyModal === 'pay'}
        onClose={() => setMoneyModal(null)}
        customerId={c.id}
      />
      <AdvanceModal
        open={moneyModal === 'advance'}
        onClose={() => setMoneyModal(null)}
        customerId={c.id}
      />
      <CustomerFormModal
        customer={editing}
        onClose={() => setEditing(null)}
        onSaved={() => {
          qc.invalidateQueries({ queryKey: ['customers'] });
        }}
      />
    </>
  );
}
