import { formatINR } from '@/utils/format';

/** Totals box — pass either live `calc` (from utils/gst) or saved document fields via `doc`. */
export default function TotalsPanel({
  calc,
  doc,
  interstate,
  extraLabel = 'Transport / other charges',
  note,
}) {
  const v = doc
    ? {
        subtotal: doc.subtotal,
        discount: doc.discount_total,
        taxable: doc.taxable_amount,
        cgst: doc.cgst_amount,
        sgst: doc.sgst_amount,
        igst: doc.igst_amount,
        extra: doc.transport_charges ?? 0,
        roundOff: doc.round_off,
        grandTotal: doc.grand_total,
      }
    : calc;
  const row = (label, value, cls = '') => (
    <div className={`flex justify-between gap-4 py-1 ${cls}`}>
      <span className="text-slate-500">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
  return (
    <div className="card text-sm">
      {row('Subtotal', formatINR(v.subtotal))}
      {Number(v.discount) > 0 && row('Discount', `− ${formatINR(v.discount)}`, 'text-green-700')}
      {row('Taxable value', formatINR(v.taxable))}
      {interstate ? (
        row('IGST', formatINR(v.igst))
      ) : (
        <>
          {row('CGST', formatINR(v.cgst))}
          {row('SGST', formatINR(v.sgst))}
        </>
      )}
      {Number(v.extra) > 0 && row(extraLabel, formatINR(v.extra))}
      {Number(v.roundOff) !== 0 &&
        row(
          'Round off',
          `${Number(v.roundOff) > 0 ? '+' : '−'} ${formatINR(Math.abs(v.roundOff))}`,
        )}
      <div className="mt-2 flex justify-between border-t border-slate-200 pt-2 text-base font-semibold dark:border-slate-700">
        <span>Grand total</span>
        <span className="tabular-nums">{formatINR(v.grandTotal)}</span>
      </div>
      {doc?.amount_in_words && (
        <p className="mt-1 text-xs italic text-slate-500">{doc.amount_in_words}</p>
      )}
      {note && <p className="mt-2 text-xs text-slate-400">{note}</p>}
    </div>
  );
}
