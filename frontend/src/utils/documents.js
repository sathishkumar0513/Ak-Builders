import { api } from '@/api/client';

/** Fetch a PDF from an authenticated endpoint (JWT header) as a Blob. */
export async function fetchPdf(url) {
  const res = await api.get(url, { responseType: 'blob' });
  return res.data;
}

export function downloadBlob(blob, filename) {
  const href = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 10_000);
}

/**
 * Open a PDF in a new tab for preview / printing. The tab is opened *before* the download
 * so pop-up blockers allow it (it must happen directly in the click handler).
 */
export async function openPdf(url) {
  const win = window.open('', '_blank');
  if (win) win.document.write('<p style="font-family:sans-serif;padding:2rem">Preparing PDF…</p>');
  try {
    const blob = await fetchPdf(url);
    const href = URL.createObjectURL(blob);
    if (win) win.location.href = href;
    else window.location.href = href;
  } catch (e) {
    win?.close();
    throw e;
  }
}

/**
 * Share a PDF to WhatsApp.
 * Phones (Android/iOS): native share sheet with the PDF file attached → pick WhatsApp.
 * Desktop: downloads the PDF and opens WhatsApp Web chat with the message (attach the file there).
 * Returns 'shared' | 'fallback' | 'cancelled'.
 */
export async function shareToWhatsApp({ pdfUrl, filename, message, phone }) {
  const blob = await fetchPdf(pdfUrl);
  const file = new File([blob], filename, { type: 'application/pdf' });
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], text: message, title: filename });
      return 'shared';
    } catch (e) {
      if (e?.name === 'AbortError') return 'cancelled';
    }
  }
  downloadBlob(blob, filename);
  const digits = String(phone || '')
    .replace(/\D/g, '')
    .slice(-10);
  window.open(
    `https://wa.me/${digits ? `91${digits}` : ''}?text=${encodeURIComponent(message)}`,
    '_blank',
    'noopener',
  );
  return 'fallback';
}
