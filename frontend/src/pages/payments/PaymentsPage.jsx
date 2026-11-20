import { useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { CheckCircle2, Download, Plus, XCircle, Ban } from 'lucide-react';
import { paymentsApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { useListParams } from '@/hooks/useListParams';
import { useLookups } from '@/hooks/useLookups';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import DataTable from '@/components/ui/DataTable';
import PageHeader from '@/components/ui/PageHeader';
import SearchInput from '@/components/ui/SearchInput';
import Badge from '@/components/ui/Badge';
import { Input, Select } from '@/components/ui/Field';
import DocumentButtons from '@/components/DocumentButtons';
import { exportCsv } from '@/utils/exportCsv';
import { formatDate, formatINR } from '@/utils/format';
import { CHEQUE_STATUS } from '@/utils/status';
import PaymentModal from './PaymentModal';
import ReasonModal from './ReasonModal';

export default function PaymentsPage() {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { hasRole } = useAuth();
  const { payment_modes } = useLookups();
  const { params, setParams, toggleOrdering } = useListParams({ ordering: '-date' });
  const [adding, setAdding] = useState(false);
  const [cancelling, setCancelling] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ['payments', params],
    queryFn: () => paymentsApi.list(params),
    placeholderData: keepPreviousData,
  });
  const total = (data?.results || []).reduce((s, p) => s + Number(p.amount), 0);
  const refresh = () =>
    ['payments', 'invoices', 'customers', 'projects'].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );

  const cheque = async (p, status) => {
    const bounced = status === 'BOUNCED';
    if (
      !(await confirm({
        title: bounced ? 'Cheque bounced?' : 'Cheque cleared?',
        message: bounced
          ? `${formatINR(p.amount)} will be added back to ${p.customer_name}'s dues and the invoice reopened.`
          : `Mark cheque ${p.cheque_number} as cleared.`,
        confirmText: bounced ? 'Mark bounced' : 'Mark cleared',
        danger: bounced,
      }))
    )
      return;
    try {
      await paymentsApi.action(p.id, 'cheque', { status });
      toast.success(bounced ? 'Marked as bounced' : 'Marked as cleared');
      refresh();
    } catch (e) {
      toast.error(getErrorMessage(e));
    }
  };

  const onExport = async () => {
    const all = await paymentsApi.list({ ...params, page: 1, page_size: 200 });
    exportCsv(
      'ak-builders-payments',
      [
        { header: 'Receipt', value: (p) => p.receipt_number },
        { header: 'Date', value: (p) => formatDate(p.date) },
        { header: 'Customer', value: (p) => p.customer_name },
        { header: 'Invoice', value: (p) => p.invoice_number },
        { header: 'Project', value: (p) => p.project_code },
        { header: 'Stage', value: (p) => p.stage_name },
        { header: 'Mode', value: (p) => p.mode_display },
        { header: 'Reference', value: (p) => p.reference_number || p.cheque_number },
        {
          header: 'Cheque status',
          value: (p) => (p.mode === 'CHEQUE' ? p.cheque_status_display : ''),
        },
        { header: 'Amount', value: (p) => p.amount },
      ],
      all.results,
    );
  };

  const columns = [
    {
      key: 'r',
      header: 'Receipt',
      sortField: 'receipt_number',
      render: (p) => (
        <div>
          <p className="font-medium">{p.receipt_number}</p>
          <p className="text-xs text-slate-500">{p.customer_name}</p>
        </div>
      ),
    },
    { key: 'date', header: 'Date', sortField: 'date', render: (p) => formatDate(p.date) },
    {
      key: 'for',
      header: 'For',
      render: (p) =>
        p.invoice ? (
          <Link to={`/invoices/${p.invoice}`} className="text-brand-700 hover:underline">
            {p.invoice_number}
          </Link>
        ) : (
          <span>
            {p.project_code} · {p.stage_name}
          </span>
        ),
    },
    {
      key: 'mode',
      header: 'Mode',
      render: (p) => (
        <span className="flex flex-wrap items-center gap-1">
          {p.mode_display}
          {p.mode === 'CHEQUE' && (
            <Badge color={CHEQUE_STATUS[p.cheque_status]}>{p.cheque_status_display}</Badge>
          )}
          <span className="text-xs text-slate-500">{p.cheque_number || p.reference_number}</span>
        </span>
      ),
    },
    {
      key: 'amt',
      header: 'Amount',
      sortField: 'amount',
      className: 'text-right',
      render: (p) => (
        <span
          className={`font-medium ${p.cheque_status === 'BOUNCED' ? 'text-red-600 line-through' : ''}`}
        >
          {formatINR(p.amount)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (p) => (
        <div className="flex justify-end" onClick={(e) => e.stopPropagation()}>
          {p.cheque_status === 'PENDING' && (
            <>
              <button
                className="btn-ghost px-2 text-green-700"
                title="Cheque cleared"
                onClick={() => cheque(p, 'CLEARED')}
              >
                <CheckCircle2 size={16} />
              </button>
              <button
                className="btn-ghost px-2 text-red-600"
                title="Cheque bounced"
                onClick={() => cheque(p, 'BOUNCED')}
              >
                <XCircle size={16} />
              </button>
            </>
          )}
          <DocumentButtons base={`/payments/${p.id}/`} compact />
          {hasRole('ADMIN') && (
            <button
              className="btn-ghost px-2 text-red-600"
              title="Cancel receipt"
              onClick={() => setCancelling(p)}
            >
              <Ban size={16} />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Payments"
        subtitle={data ? `${data.count} receipts · ${formatINR(total)} on this page` : ' '}
        actions={
          <>
            <button className="btn-secondary" onClick={onExport}>
              <Download size={16} /> Export CSV
            </button>
            <button className="btn-primary" onClick={() => setAdding(true)}>
              <Plus size={16} /> Record payment
            </button>
          </>
        }
      />
      <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-[1fr_150px_170px_150px_150px]">
        <SearchInput
          value={params.search || ''}
          onChange={(v) => setParams({ search: v })}
          placeholder="Receipt, customer, invoice, UTR, cheque"
        />
        <Select
          value={params.mode || ''}
          onChange={(e) => setParams({ mode: e.target.value })}
          placeholder="All modes"
          options={payment_modes}
        />
        <Select
          value={params.cheque_status || ''}
          onChange={(e) => setParams({ cheque_status: e.target.value })}
          placeholder="Any cheque status"
          options={[
            { value: 'PENDING', label: 'Cheques pending' },
            { value: 'CLEARED', label: 'Cleared' },
            { value: 'BOUNCED', label: 'Bounced' },
          ]}
        />
        <Input
          type="date"
          value={params.date_from || ''}
          onChange={(e) => setParams({ date_from: e.target.value })}
          title="From"
        />
        <Input
          type="date"
          value={params.date_to || ''}
          onChange={(e) => setParams({ date_to: e.target.value })}
          title="To"
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
        emptyText="No payments recorded yet."
      />
      <PaymentModal open={adding} onClose={() => setAdding(false)} />
      <ReasonModal
        open={!!cancelling}
        onClose={() => setCancelling(null)}
        title={`Cancel receipt ${cancelling?.receipt_number || ''}?`}
        description="The amount is added back to the customer's dues and the invoice is reopened."
        confirmText="Cancel receipt"
        onConfirm={async (reason) => {
          await paymentsApi.action(cancelling.id, 'cancel', { reason });
          toast.success('Receipt cancelled');
          refresh();
        }}
      />
    </>
  );
}
