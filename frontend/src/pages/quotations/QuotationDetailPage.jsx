import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  Check,
  Copy,
  Download,
  Eye,
  FolderKanban,
  GitBranch,
  Mail,
  MessageCircle,
  MoreHorizontal,
  Pencil,
  Receipt,
  Send,
  Trash2,
  X,
} from 'lucide-react';
import { quotationsApi } from '@/api/services';
import { getErrorMessage } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { useConfirm } from '@/components/ui/ConfirmDialog';
import PageHeader from '@/components/ui/PageHeader';
import BackLink from '@/components/ui/BackLink';
import Badge from '@/components/ui/Badge';
import InfoGrid from '@/components/ui/InfoGrid';
import Spinner from '@/components/ui/Spinner';
import TotalsPanel from '@/components/lineitems/TotalsPanel';
import { downloadBlob, fetchPdf, openPdf, shareToWhatsApp } from '@/utils/documents';
import { formatDate, formatDateTime, formatINR, formatQty } from '@/utils/format';
import { QUOTATION_STATUS } from '@/utils/status';
import { ConvertModal, EmailModal, RejectModal } from './QuotationModals';

export default function QuotationDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { hasRole } = useAuth();
  const [modal, setModal] = useState(null);
  const [busy, setBusy] = useState('');
  const [moreOpen, setMoreOpen] = useState(false);
  const { data: q, isLoading } = useQuery({
    queryKey: ['quotations', id],
    queryFn: () => quotationsApi.get(id),
  });

  if (isLoading || !q) return <div className="card h-64 animate-pulse" />;
  const can = (a) => q.allowed_actions.includes(a);
  const pdfUrl = `/quotations/${q.id}/pdf/`;
  const filename = `Quotation-${q.number.replace(/\//g, '-')}-R${q.revision}.pdf`;
  const refresh = (data) => {
    if (data?.id) qc.setQueryData(['quotations', String(data.id)], data);
    qc.invalidateQueries({ queryKey: ['quotations'] });
    qc.invalidateQueries({ queryKey: ['customers'] });
  };

  const run = async (key, fn, success) => {
    setBusy(key);
    try {
      const r = await fn();
      if (success) toast.success(success);
      return r;
    } catch (e) {
      toast.error(getErrorMessage(e));
      return null;
    } finally {
      setBusy('');
    }
  };

  const doAction = (name, msg) =>
    run(name, () => quotationsApi.action(q.id, name), msg).then((r) => r && refresh(r));

  const onWhatsApp = async () => {
    const s = await run('wa', () => quotationsApi.detail(q.id, 'share-text'));
    if (!s) return;
    const result = await run('wa', () =>
      shareToWhatsApp({ pdfUrl, filename: s.filename, message: s.message, phone: s.phone }),
    );
    if (result === 'fallback')
      toast('PDF downloaded — attach it in the WhatsApp chat that just opened.', {
        icon: '📎',
        duration: 6000,
      });
    if (
      result &&
      result !== 'cancelled' &&
      q.status === 'DRAFT' &&
      (await confirm({
        title: 'Mark as sent?',
        message: 'Mark this quotation as sent to the customer?',
        confirmText: 'Mark as sent',
      }))
    ) {
      doAction('send', 'Marked as sent');
    }
  };

  const onRevise = async () => {
    if (
      !(await confirm({
        title: `Create Rev ${q.revision + 1}?`,
        message:
          'A new draft revision is created with the same number and items. This revision stays in the history unchanged.',
        confirmText: 'Create revision',
      }))
    )
      return;
    const r = await run(
      'revise',
      () => quotationsApi.action(q.id, 'revise'),
      `Rev ${q.revision + 1} created`,
    );
    if (r) {
      refresh(r);
      navigate(`/quotations/${r.id}/edit`);
    }
  };

  const onDuplicate = async () => {
    const r = await run(
      'dup',
      () => quotationsApi.action(q.id, 'duplicate', {}),
      'Copied as a new quotation',
    );
    if (r) {
      refresh(r);
      navigate(`/quotations/${r.id}/edit`);
    }
  };

  const onDelete = async () => {
    if (
      !(await confirm({
        title: 'Delete quotation?',
        message: `${q.number} Rev ${q.revision} will be removed.`,
        confirmText: 'Delete',
        danger: true,
      }))
    )
      return;
    if (await run('del', () => quotationsApi.remove(q.id), 'Quotation deleted')) {
      refresh();
      navigate(q.previous_revision ? `/quotations/${q.previous_revision}` : '/quotations');
    }
  };

  const btn = (key, label, Icon, onClick, cls = 'btn-secondary') => (
    <button key={key} className={cls} onClick={onClick} disabled={!!busy}>
      {busy === key ? <Spinner /> : <Icon size={16} />} {label}
    </button>
  );

  const primary = [];
  if (can('edit'))
    primary.push(
      <Link key="edit" to={`/quotations/${q.id}/edit`} className="btn-secondary">
        <Pencil size={16} /> Edit
      </Link>,
    );
  if (can('send') && q.status === 'DRAFT')
    primary.push(btn('send', 'Mark as sent', Send, () => doAction('send', 'Marked as sent')));
  if (can('approve'))
    primary.push(
      btn(
        'approve',
        'Customer approved',
        Check,
        () => doAction('approve', 'Quotation approved'),
        'btn-primary',
      ),
    );
  if (can('convert') && hasRole('ADMIN'))
    primary.push(
      btn('convert', 'Convert to project', FolderKanban, () => setModal('convert'), 'btn-primary'),
    );
  primary.push(btn('wa', 'WhatsApp', MessageCircle, onWhatsApp));
  primary.push(btn('pdf', 'PDF', Eye, () => run('pdf', () => openPdf(pdfUrl))));

  const more = [
    [
      'Download PDF',
      Download,
      () => run('dl', async () => downloadBlob(await fetchPdf(pdfUrl), filename)),
    ],
    ['Email', Mail, () => setModal('email')],
    can('reject') && ['Customer rejected', X, () => setModal('reject')],
    can('revise') && [`Revise (create Rev ${q.revision + 1})`, GitBranch, onRevise],
    ['Duplicate as new quotation', Copy, onDuplicate],
    ['APPROVED', 'CONVERTED'].includes(q.status) &&
      hasRole('ADMIN', 'ACCOUNTANT') && [
        'Create invoice from this quotation',
        Receipt,
        () => navigate(`/invoices/new?quotation=${q.id}`),
      ],
    can('delete') && hasRole('ADMIN') && ['Delete', Trash2, onDelete, 'text-red-600'],
  ].filter(Boolean);

  const timeline = [
    [
      'Created',
      formatDateTime(q.created_at) + (q.created_by_name ? ` by ${q.created_by_name}` : ''),
    ],
    q.sent_at && ['Sent', formatDateTime(q.sent_at)],
    q.approved_at && ['Approved', formatDateTime(q.approved_at)],
    q.rejection_reason && ['Rejection reason', q.rejection_reason],
  ].filter(Boolean);

  return (
    <>
      <BackLink to="/quotations">All quotations</BackLink>
      <PageHeader
        title={
          <span>
            {q.number}{' '}
            <span className="text-base font-normal text-slate-500">Rev {q.revision}</span>
          </span>
        }
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <Link to={`/customers/${q.customer}`} className="hover:underline">
              {q.customer_detail.name}
            </Link>
            <Badge color={QUOTATION_STATUS[q.status]}>{q.status_display}</Badge>
            {!q.is_latest && <Badge color="amber">Old revision</Badge>}
          </span>
        }
        actions={
          <>
            {primary}
            <div className="relative">
              <button
                className="btn-secondary px-2"
                onClick={() => setMoreOpen((o) => !o)}
                aria-label="More actions"
                aria-expanded={moreOpen}
              >
                <MoreHorizontal size={18} />
              </button>
              {moreOpen && (
                <div
                  className="absolute right-0 z-20 mt-1 w-60 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800"
                  onMouseLeave={() => setMoreOpen(false)}
                >
                  {more.map(([label, Icon, onClick, cls]) => (
                    <button
                      key={label}
                      className={`flex w-full items-center gap-2 px-4 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-700 ${cls || ''}`}
                      onClick={() => {
                        setMoreOpen(false);
                        onClick();
                      }}
                    >
                      <Icon size={15} /> {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </>
        }
      />

      {!q.is_latest && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
          You are viewing an old revision.{' '}
          <Link
            className="font-medium underline"
            to={`/quotations/${q.revisions.find((r) => r.is_latest)?.id}`}
          >
            Open the latest revision
          </Link>
        </div>
      )}
      {q.project && (
        <div className="mb-3 rounded-lg border border-purple-200 bg-purple-50 px-3 py-2 text-sm text-purple-800 dark:border-purple-800 dark:bg-purple-900/30 dark:text-purple-200">
          Converted to project{' '}
          <Link to={`/projects/${q.project.id}`} className="font-semibold underline">
            {q.project.code}
          </Link>{' '}
          — {q.project.name}.
        </div>
      )}

      <div className="mb-4 grid gap-4 lg:grid-cols-[1fr_300px]">
        <div className="card">
          <InfoGrid
            cols="sm:grid-cols-2 lg:grid-cols-3"
            items={[
              ['Work', q.title],
              ['Quotation date', formatDate(q.quotation_date)],
              ['Valid until', formatDate(q.valid_until)],
              ['Customer mobile', q.customer_detail.phone],
              ['Customer GSTIN', q.customer_detail.gstin],
              ['Tax', q.is_interstate ? 'IGST (other state)' : 'CGST + SGST'],
              ['Site address', q.site_address],
            ]}
          />
        </div>
        <div className="card text-sm">
          <p className="mb-2 font-semibold">Revisions</p>
          <ul className="space-y-1">
            {q.revisions.map((r) => (
              <li key={r.id}>
                <Link
                  to={`/quotations/${r.id}`}
                  className={`flex justify-between rounded px-2 py-1 ${r.id === q.id ? 'bg-brand-50 font-medium dark:bg-slate-700' : 'hover:bg-slate-50 dark:hover:bg-slate-700'}`}
                >
                  <span>
                    Rev {r.revision} ·{' '}
                    <Badge color={QUOTATION_STATUS[r.status]}>{r.status.toLowerCase()}</Badge>
                  </span>
                  <span className="tabular-nums">{formatINR(r.grand_total)}</span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-3 space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-500 dark:border-slate-700">
            {timeline.map(([k, v]) => (
              <p key={k}>
                <b>{k}:</b> {v}
              </p>
            ))}
          </div>
        </div>
      </div>

      <div className="card mb-4 overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900/40">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="text-left">Description</th>
              <th className="text-left">HSN/SAC</th>
              <th className="text-right">Qty</th>
              <th className="text-right">Rate</th>
              <th className="text-right">Disc</th>
              <th className="text-right">Taxable</th>
              <th className="text-right">GST</th>
              <th className="px-3 text-right">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {q.items.map((i, n) => (
              <tr key={i.id}>
                <td className="px-3 py-2">{n + 1}</td>
                <td>
                  {i.description}
                  {i.item_type === 'SERVICE' && <Badge className="ml-1">service</Badge>}
                </td>
                <td className="text-xs">{i.hsn_code}</td>
                <td className="text-right">
                  {formatQty(i.quantity)} {i.unit_display}
                </td>
                <td className="text-right">{formatINR(i.rate)}</td>
                <td className="text-right">
                  {Number(i.discount_percent) ? `${Number(i.discount_percent)}%` : '—'}
                </td>
                <td className="text-right">{formatINR(i.taxable_amount)}</td>
                <td className="text-right">{Number(i.gst_rate)}%</td>
                <td className="px-3 text-right font-medium">{formatINR(i.line_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="card space-y-3 text-sm">
          {q.notes && (
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Notes</p>
              <p className="whitespace-pre-line">{q.notes}</p>
            </div>
          )}
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">Terms &amp; conditions</p>
            <p className="whitespace-pre-line text-slate-600 dark:text-slate-300">
              {q.terms_and_conditions || '—'}
            </p>
          </div>
        </div>
        <TotalsPanel doc={{ ...q, transport_charges: 0 }} interstate={q.is_interstate} />
      </div>

      <RejectModal
        quotation={q}
        open={modal === 'reject'}
        onClose={() => setModal(null)}
        onDone={refresh}
      />
      <EmailModal
        quotation={q}
        open={modal === 'email'}
        onClose={() => setModal(null)}
        onDone={refresh}
      />
      <ConvertModal
        quotation={q}
        open={modal === 'convert'}
        onClose={() => setModal(null)}
        onDone={(r) => refresh(r.quotation)}
      />
    </>
  );
}
