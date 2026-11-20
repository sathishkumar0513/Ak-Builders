import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { calculateDocument, splitTaxPaise } from './gst';

// The same 300 cases are checked on the server by backend/apps/core/tests/test_gst_parity.py
const cases = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../backend/apps/core/tests/gst_cases.json', import.meta.url)),
    'utf8',
  ),
);

const money = (v) => Number(v).toFixed(2);

describe('GST preview matches the server to the paisa', () => {
  it('has the shared cases', () => expect(cases).toHaveLength(300));

  it.each(cases.map((c, i) => [i, c]))('case %i', (_, c) => {
    const t = calculateDocument(c.lines, {
      interstate: c.interstate,
      headerDiscount: c.header_discount,
      extraCharges: c.extra_charges,
    });
    const e = c.expected;
    expect({
      subtotal: money(t.subtotal),
      discount: money(t.discount),
      taxable: money(t.taxable),
      cgst: money(t.cgst),
      sgst: money(t.sgst),
      igst: money(t.igst),
      roundOff: money(t.roundOff),
      grandTotal: money(t.grandTotal),
    }).toEqual({
      subtotal: money(e.subtotal),
      discount: money(e.discount),
      taxable: money(e.taxable),
      cgst: money(e.cgst),
      sgst: money(e.sgst),
      igst: money(e.igst),
      roundOff: money(e.roundOff),
      grandTotal: money(e.grandTotal),
    });
    t.lines.forEach((l, j) => {
      expect(money(l.taxable)).toBe(money(e.lines[j].taxable));
      expect(money(l.total)).toBe(money(e.lines[j].total));
    });
  });
});

describe('splitTaxPaise', () => {
  it('gives the odd paisa to CGST inside Tamil Nadu', () => {
    expect(splitTaxPaise(1001, 18, false)).toEqual({ cgst: 90, sgst: 90, igst: 0 });
    expect(splitTaxPaise(1003, 5, false)).toEqual({ cgst: 25, sgst: 25, igst: 0 });
    expect(splitTaxPaise(1010, 5, false)).toEqual({ cgst: 26, sgst: 25, igst: 0 });
  });
  it('uses IGST across states', () => {
    expect(splitTaxPaise(10000, 28, true)).toEqual({ cgst: 0, sgst: 0, igst: 2800 });
  });
});
