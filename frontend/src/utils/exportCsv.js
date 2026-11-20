/**
 * Text starting with = + - @ could run as a formula when the CSV is opened in Excel
 * (e.g. a customer named "=HYPERLINK(...)"). Such text gets a leading apostrophe; plain
 * numbers like -250.00 are left alone.
 */
export function csvCell(v) {
  let s = v === null || v === undefined ? '' : String(v);
  if (/^[=+\-@\t\r]/.test(s) && !/^[-+]?\d+(\.\d+)?$/.test(s)) s = `'${s}`;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/**
 * Download rows as CSV (opens in Excel). columns: [{ header, value: (row) => any }]
 * Adds a UTF-8 BOM so ₹ and Tamil text show correctly in Excel.
 */
export function exportCsv(filename, columns, rows) {
  const escape = csvCell;
  const lines = [columns.map((c) => escape(c.header)).join(',')];
  rows.forEach((row) => lines.push(columns.map((c) => escape(c.value(row))).join(',')));
  const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
