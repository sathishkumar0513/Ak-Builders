import { describe, expect, it } from 'vitest';
import { formatDate, formatINR, formatQty } from './format';
import { compactINR } from './chart';
import { csvCell } from './exportCsv';

describe('Indian formatting', () => {
  it('groups rupees in lakhs and crores', () => {
    expect(formatINR(1234567.5)).toBe('₹12,34,567.50');
    expect(formatINR(0)).toBe('₹0.00');
    expect(formatINR('99.999')).toBe('₹100.00');
  });
  it('shows dates as DD/MM/YYYY', () => {
    expect(formatDate('2026-11-05')).toBe('05/11/2026');
    expect(formatDate(null)).toBe('');
  });
  it('trims quantities', () => {
    expect(formatQty('150.000')).toBe('150');
    expect(formatQty('12.500')).toBe('12.5');
  });
  it('short chart labels', () => {
    expect(compactINR(181978)).toBe('₹1.82 L');
    expect(compactINR(25000000)).toBe('₹2.50 Cr');
    expect(compactINR(45000)).toBe('₹45K');
    expect(compactINR(0)).toBe('₹0');
  });
});

describe('CSV export safety', () => {
  it('neutralises spreadsheet formulas but keeps numbers', () => {
    expect(csvCell('=HYPERLINK("x")')).toBe(`"'=HYPERLINK(""x"")"`);
    expect(csvCell('@SUM(A1)')).toBe("'@SUM(A1)");
    expect(csvCell('+91 98765')).toBe("'+91 98765");
    expect(csvCell('-250.00')).toBe('-250.00');
    expect(csvCell('Ravi, Kumar')).toBe('"Ravi, Kumar"');
    expect(csvCell(null)).toBe('');
  });
});
