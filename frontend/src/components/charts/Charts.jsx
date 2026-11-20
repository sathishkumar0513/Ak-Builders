import { useState } from 'react';
import { formatINR } from '@/utils/format';
import { CHART_COLORS, compactINR } from '@/utils/chart';

/** Small, dependency-free SVG charts (work offline, follow dark mode via currentColor). */

function niceMax(v) {
  if (v <= 0) return 1000;
  const p = 10 ** Math.floor(Math.log10(v / 4));
  const step = [1, 2, 2.5, 5, 10].find((m) => m * p >= v / 4) * p;
  return step * 4;
}

/** Grouped vertical bars. data: [{label, [key]: number}], series: [{key, label, color}] */
export function BarChart({ data, series, height = 230 }) {
  const [hover, setHover] = useState(null);
  const W = 640;
  const H = height;
  const pad = { l: 52, r: 8, t: 10, b: 26 };
  const max = niceMax(
    Math.max(0, ...data.flatMap((d) => series.map((s) => Number(d[s.key]) || 0))),
  );
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;
  const slot = plotW / Math.max(data.length, 1);
  const barW = Math.min(18, (slot * 0.75) / series.length);
  const y = (v) => pad.t + plotH - (Math.max(0, Number(v) || 0) / max) * plotH;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img">
        {[0, 1, 2, 3, 4].map((i) => {
          const v = (max / 4) * i;
          return (
            <g key={i}>
              <line
                x1={pad.l}
                x2={W - pad.r}
                y1={y(v)}
                y2={y(v)}
                className="stroke-slate-200 dark:stroke-slate-700"
                strokeDasharray={i ? '3 3' : undefined}
              />
              <text
                x={pad.l - 6}
                y={y(v) + 3}
                textAnchor="end"
                className="fill-slate-400 text-[10px]"
              >
                {compactINR(v)}
              </text>
            </g>
          );
        })}
        {data.map((d, i) => {
          const x0 = pad.l + slot * i + (slot - barW * series.length) / 2;
          return (
            <g
              key={d.label}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onClick={() => setHover(hover === i ? null : i)}
            >
              <rect
                x={pad.l + slot * i}
                y={pad.t}
                width={slot}
                height={plotH}
                className={hover === i ? 'fill-slate-100 dark:fill-slate-800' : 'fill-transparent'}
              />
              {series.map((s, j) => {
                const top = y(d[s.key]);
                return (
                  <rect
                    key={s.key}
                    x={x0 + j * barW}
                    y={top}
                    width={barW - 2}
                    height={Math.max(pad.t + plotH - top, 0)}
                    rx={2}
                    fill={s.color}
                  />
                );
              })}
              <text
                x={pad.l + slot * i + slot / 2}
                y={H - 8}
                textAnchor="middle"
                className="fill-slate-500 text-[10px]"
              >
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
      {hover !== null && data[hover] && (
        <div className="pointer-events-none absolute right-2 top-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow dark:border-slate-700 dark:bg-slate-800">
          <p className="mb-1 font-semibold">{data[hover].label}</p>
          {series.map((s) => (
            <p key={s.key} className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.label}: <b>{formatINR(data[hover][s.key])}</b>
            </p>
          ))}
        </div>
      )}
      <Legend items={series.map((s) => ({ label: s.label, color: s.color }))} />
    </div>
  );
}

export function Legend({ items }) {
  return (
    <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-slate-500">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: i.color }} />
          {i.label}
          {i.value !== undefined && <b className="text-slate-700 dark:text-slate-200">{i.value}</b>}
        </span>
      ))}
    </div>
  );
}

/** Donut with centre total. items: [{label, value}] */
export function DonutChart({ items, format = compactINR, centerLabel = 'Total' }) {
  const total = items.reduce((s, i) => s + Number(i.value || 0), 0);
  const R = 60;
  const C = 2 * Math.PI * R;
  let offset = 0;
  return (
    <div>
      <svg viewBox="0 0 160 160" className="mx-auto h-40 w-40">
        <circle
          cx="80"
          cy="80"
          r={R}
          fill="none"
          strokeWidth="20"
          className="stroke-slate-100 dark:stroke-slate-700"
        />
        {total > 0 &&
          items.map((it, i) => {
            const len = (Number(it.value) / total) * C;
            const el = (
              <circle
                key={it.label}
                cx="80"
                cy="80"
                r={R}
                fill="none"
                stroke={CHART_COLORS[i % CHART_COLORS.length]}
                strokeWidth="20"
                strokeDasharray={`${len} ${C - len}`}
                strokeDashoffset={-offset}
                transform="rotate(-90 80 80)"
              >
                <title>
                  {it.label}: {formatINR(it.value)}
                </title>
              </circle>
            );
            offset += len;
            return el;
          })}
        <text x="80" y="76" textAnchor="middle" className="fill-slate-400 text-[10px]">
          {centerLabel}
        </text>
        <text x="80" y="94" textAnchor="middle" className="fill-current text-[15px] font-semibold">
          {format(total)}
        </text>
      </svg>
      <Legend
        items={items.map((it, i) => ({
          label: it.label,
          color: CHART_COLORS[i % CHART_COLORS.length],
          value: total ? `${Math.round((Number(it.value) / total) * 100)}%` : '',
        }))}
      />
    </div>
  );
}

/** Horizontal bars for "top N" lists. items: [{label, value, sub?, to?}] */
export function HBarList({ items, format = formatINR, color = CHART_COLORS[0] }) {
  const max = Math.max(1, ...items.map((i) => Number(i.value) || 0));
  return (
    <ul className="space-y-3">
      {items.map((it) => (
        <li key={it.label}>
          <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
            <span className="truncate">{it.label}</span>
            <span className="shrink-0 font-medium">{format(it.value)}</span>
          </div>
          <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-700">
            <div
              className="h-2 rounded-full"
              style={{ width: `${(Number(it.value) / max) * 100}%`, background: color }}
            />
          </div>
          {it.sub && <p className="mt-0.5 text-xs text-slate-500">{it.sub}</p>}
        </li>
      ))}
    </ul>
  );
}
