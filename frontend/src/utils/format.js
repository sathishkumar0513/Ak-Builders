/** India formatting helpers: ₹ with lakh/crore grouping, DD/MM/YYYY dates. */
const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
});
const inrShort = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

export const formatINR = (value) => inr.format(Number(value || 0));
export const formatNumber = (value) => inrShort.format(Number(value || 0));

/** "2026-11-11" or Date → "11/11/2026" */
export function formatDate(value) {
  if (!value) return '';
  const d =
    typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
      ? new Date(`${value}T00:00:00`)
      : new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}/${mm}/${d.getFullYear()}`;
}

/** "11/11/2026" → "2026-11-11" (API format) */
export function toApiDate(ddmmyyyy) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(ddmmyyyy || '');
  return m ? `${m[3]}-${m[2]}-${m[1]}` : ddmmyyyy;
}

/** ISO datetime → "11/11/2026 05:30 PM" */
export function formatDateTime(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const time = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
  return `${formatDate(d)} ${time.toUpperCase()}`;
}

/** "120.500" → "120.5", "10.000" → "10" */
export function formatQty(value) {
  const n = Number(value || 0);
  return n.toLocaleString('en-IN', { maximumFractionDigits: 3 });
}

/** Today in API format (YYYY-MM-DD), local time zone. */
export function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
