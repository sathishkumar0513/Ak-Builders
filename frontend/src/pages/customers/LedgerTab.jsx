import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Download } from 'lucide-react';
import { customersApi } from '@/api/services';
import { Input } from '@/components/ui/Field';
import { exportCsv } from '@/utils/exportCsv';
import { formatDate, formatINR } from '@/utils/format';

const linkFor = (r) => {
  const map = { 'invoices.Invoice': 'invoices', 'payments.AdvancePayment': 'advances' };
  return map[r.reference_type] ? `/${map[r.reference_type]}/${r.reference_id}` : null;
};
const bal = (v) => {
  const n = Number(v);
  if (n === 0) return <span className="text-slate-500">₹0.00</span>;
  return n > 0 ? (
    <span className="text-red-600">{formatINR(n)} Dr</span>
  ) : (
    <span className="text-green-700">{formatINR(-n)} Cr</span>
  );
};

/** Customer statement: Dr = customer owes us, Cr = we hold the customer's money. */
export default function LedgerTab({ customer }) {
  const [range, setRange] = useState({ date_from: '', date_to: '' });
  const { data, isLoading } = useQuery({
    queryKey: ['customers', String(customer.id), 'ledger', range],
    queryFn: () => customersApi.detail(customer.id, 'ledger', range),
  });
  const onExport = () =>
    exportCsv(
      `ledger-${customer.name}`,
      [
        { header: 'Date', value: (r) => formatDate(r.date) },
        { header: 'Type', value: (r) => r.entry_type_display },
        { header: 'Reference', value: (r) => r.reference_number },
        { header: 'Project', value: (r) => r.project },
        { header: 'Narration', value: (r) => r.narration },
        { header: 'Debit', value: (r) => r.debit },
        { header: 'Credit', value: (r) => r.credit },
        { header: 'Balance', value: (r) => r.balance },
      ],
      [
        {
          date: range.date_from,
          entry_type_display: 'Opening balance',
          reference_number: '',
          project: '',
          narration: '',
          debit: '',
          credit: '',
          balance: data.opening_balance,
        },
        ...data.rows,
      ],
    );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-sm">
          From{' '}
          <Input
            type="date"
            className="w-auto"
            value={range.date_from}
            onChange={(e) => setRange({ ...range, date_from: e.target.value })}
          />
        </label>
        <label className="text-sm">
          To{' '}
          <Input
            type="date"
            className="w-auto"
            value={range.date_to}
            onChange={(e) => setRange({ ...range, date_to: e.target.value })}
          />
        </label>
        <div className="flex-1" />
        <button className="btn-secondary" onClick={onExport} disabled={!data}>
          <Download size={16} /> Export CSV
        </button>
      </div>
      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900/40">
            <tr>
              <th className="px-3 py-2 text-left">Date</th>
              <th className="text-left">Particulars</th>
              <th className="text-left">Ref.</th>
              <th className="text-right">Debit</th>
              <th className="text-right">Credit</th>
              <th className="px-3 text-right">Balance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {isLoading && (
              <tr>
                <td colSpan={6} className="p-6">
                  <div className="h-4 animate-pulse rounded bg-slate-200" />
                </td>
              </tr>
            )}
            {data && (
              <tr className="bg-slate-50/60 dark:bg-slate-900/30">
                <td className="px-3 py-2" />
                <td colSpan={4} className="font-medium">
                  Opening balance
                </td>
                <td className="px-3 text-right">{bal(data.opening_balance)}</td>
              </tr>
            )}
            {data?.rows.map((r) => (
              <tr key={r.id}>
                <td className="whitespace-nowrap px-3 py-2">{formatDate(r.date)}</td>
                <td>
                  <span className="font-medium">{r.entry_type_display}</span>
                  <span className="block text-xs text-slate-500">{r.narration}</span>
                </td>
                <td className="whitespace-nowrap text-xs">
                  {linkFor(r) ? (
                    <Link to={linkFor(r)} className="text-brand-700 hover:underline">
                      {r.reference_number}
                    </Link>
                  ) : (
                    r.reference_number
                  )}
                </td>
                <td className="text-right tabular-nums">
                  {Number(r.debit) ? formatINR(r.debit) : ''}
                </td>
                <td className="text-right tabular-nums">
                  {Number(r.credit) ? formatINR(r.credit) : ''}
                </td>
                <td className="whitespace-nowrap px-3 text-right tabular-nums">{bal(r.balance)}</td>
              </tr>
            ))}
            {data && (
              <tr className="border-t-2 border-slate-300 font-semibold dark:border-slate-600">
                <td className="px-3 py-2" />
                <td colSpan={2}>Closing balance</td>
                <td className="text-right">{formatINR(data.total_debit)}</td>
                <td className="text-right">{formatINR(data.total_credit)}</td>
                <td className="px-3 text-right">{bal(data.closing_balance)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">
        Dr = amount the customer owes · Cr = customer&apos;s money with us (unused advance).
      </p>
    </div>
  );
}
