/**
 * Live GST preview — mirrors apps/core/calculations.py exactly (integer paise, round half-up).
 * The server recalculates on save and is always the source of truth.
 */
const toNum = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
};
const roundHalfUp = (x) => Math.sign(x) * Math.round(Math.abs(x) + 1e-9);
const paise = (rupees) => roundHalfUp(toNum(rupees) * 100);

export function splitTaxPaise(taxablePaise, gstRate, interstate) {
  const tax = roundHalfUp((taxablePaise * toNum(gstRate)) / 100);
  if (interstate) return { cgst: 0, sgst: 0, igst: tax };
  const half = roundHalfUp(tax / 2);
  return { cgst: half, sgst: tax - half, igst: 0 };
}

export function calculateDocument(
  items,
  { interstate = false, headerDiscount = 0, extraCharges = 0 } = {},
) {
  const prepared = items.map((it) => {
    const qty = Math.round(toNum(it.quantity) * 1000) / 1000;
    const gross = roundHalfUp(qty * paise(it.rate));
    const discount = roundHalfUp((gross * toNum(it.discount_percent)) / 100);
    return { gross, discount, taxable: gross - discount, gst: toNum(it.gst_rate) };
  });

  // spread header discount over lines by taxable value (last line takes the remainder)
  const hd = paise(headerDiscount);
  const taxableBefore = prepared.reduce((s, p) => s + p.taxable, 0);
  if (hd > 0 && taxableBefore > 0) {
    let remaining = Math.min(hd, taxableBefore);
    prepared.forEach((p, i) => {
      let share =
        i === prepared.length - 1 ? remaining : roundHalfUp((hd * p.taxable) / taxableBefore);
      share = Math.min(share, p.taxable, remaining);
      p.discount += share;
      p.taxable -= share;
      remaining -= share;
    });
  }

  const t = { subtotal: 0, discount: 0, taxable: 0, cgst: 0, sgst: 0, igst: 0, lines: [] };
  prepared.forEach((p) => {
    const tax = splitTaxPaise(p.taxable, p.gst, interstate);
    const total = p.taxable + tax.cgst + tax.sgst + tax.igst;
    t.lines.push({ ...p, ...tax, total });
    t.subtotal += p.gross;
    t.discount += p.discount;
    t.taxable += p.taxable;
    t.cgst += tax.cgst;
    t.sgst += tax.sgst;
    t.igst += tax.igst;
  });
  const extra = paise(extraCharges);
  const raw = t.taxable + t.cgst + t.sgst + t.igst + extra;
  const grand = roundHalfUp(raw / 100) * 100;
  const r = (v) => v / 100;
  return {
    subtotal: r(t.subtotal),
    discount: r(t.discount),
    taxable: r(t.taxable),
    cgst: r(t.cgst),
    sgst: r(t.sgst),
    igst: r(t.igst),
    extra: r(extra),
    roundOff: r(grand - raw),
    grandTotal: r(grand),
    lines: t.lines.map((l) => ({
      taxable: r(l.taxable),
      discount: r(l.discount),
      tax: r(l.cgst + l.sgst + l.igst),
      total: r(l.total),
    })),
  };
}
