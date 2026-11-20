/** Shared chart colours and short ₹ labels. */
export const CHART_COLORS = ['#ea580c', '#10b981', '#3b82f6', '#a855f7', '#f59e0b', '#64748b'];

/** ₹1.25 Cr / ₹4.5 L / ₹12K — short labels for axes and tiles. */
export function compactINR(v) {
  const n = Number(v || 0);
  const a = Math.abs(n);
  const s = n < 0 ? '-' : '';
  if (a >= 1e7) return `${s}₹${(a / 1e7).toFixed(a >= 1e8 ? 0 : 2)} Cr`;
  if (a >= 1e5) return `${s}₹${(a / 1e5).toFixed(a >= 1e6 ? 1 : 2)} L`;
  if (a >= 1e3) return `${s}₹${(a / 1e3).toFixed(a >= 1e4 ? 0 : 1)}K`;
  return `${s}₹${a.toFixed(0)}`;
}
