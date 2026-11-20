import { useState } from 'react';
import toast from 'react-hot-toast';
import { Download, Eye, MessageCircle } from 'lucide-react';
import { api, getErrorMessage } from '@/api/client';
import Spinner from '@/components/ui/Spinner';
import { downloadBlob, fetchPdf, openPdf, shareToWhatsApp } from '@/utils/documents';

/**
 * PDF preview / download / WhatsApp share for any document endpoint that has
 * `{base}pdf/` and `{base}share-text/` (quotations, invoices, receipts, advances).
 */
export default function DocumentButtons({
  base,
  shareQuery = '',
  compact = false,
  onShared,
  labels = {},
}) {
  const [busy, setBusy] = useState('');
  const run = async (key, fn) => {
    setBusy(key);
    try {
      return await fn();
    } catch (e) {
      toast.error(getErrorMessage(e));
      return null;
    } finally {
      setBusy('');
    }
  };
  const share = () =>
    run('wa', async () => {
      const { data } = await api.get(`${base}share-text/${shareQuery}`);
      const r = await shareToWhatsApp({
        pdfUrl: `${base}pdf/`,
        filename: data.filename,
        message: data.message,
        phone: data.phone,
      });
      if (r === 'fallback')
        toast('PDF downloaded — attach it in the WhatsApp chat that just opened.', {
          icon: '📎',
          duration: 6000,
        });
      if (r && r !== 'cancelled') onShared?.();
    });
  const cls = compact ? 'btn-ghost px-2' : 'btn-secondary';
  const icon = (key, Icon) => (busy === key ? <Spinner /> : <Icon size={16} />);
  return (
    <>
      <button
        type="button"
        className={cls}
        onClick={share}
        disabled={!!busy}
        title="Share on WhatsApp"
      >
        {icon('wa', MessageCircle)} {!compact && (labels.whatsapp || 'WhatsApp')}
      </button>
      <button
        type="button"
        className={cls}
        onClick={() => run('pdf', () => openPdf(`${base}pdf/`))}
        disabled={!!busy}
        title="Open PDF"
      >
        {icon('pdf', Eye)} {!compact && 'PDF'}
      </button>
      {!compact && (
        <button
          type="button"
          className={cls}
          disabled={!!busy}
          title="Download PDF"
          onClick={() =>
            run('dl', async () => {
              const { data } = await api.get(`${base}share-text/`);
              downloadBlob(await fetchPdf(`${base}pdf/`), data.filename);
            })
          }
        >
          {icon('dl', Download)}
        </button>
      )}
    </>
  );
}
