import { useFieldArray, useWatch } from 'react-hook-form';
import { Plus, Trash2, Wrench } from 'lucide-react';
import clsx from 'clsx';
import MaterialPicker from './MaterialPicker';
import { formatINR } from '@/utils/format';
import { calculateDocument } from '@/utils/gst';
import { GST_RATES, emptyMaterialLine, emptyServiceLine } from './lineDefaults';

/**
 * Dynamic line-item table for purchases, quotations and invoices.
 * - Material lines: picker auto-fills description, unit, HSN, GST and rate (priceField)
 * - Service lines: free text (labour, work items, transport)
 * Desktop: a table; phone: stacked cards. Uses react-hook-form `control` with field name "items".
 */
export default function LineItemsEditor({
  control,
  register,
  setValue,
  errors,
  units,
  interstate,
  priceField = 'selling_price',
  disabled,
  headerDiscount = 0,
}) {
  const { fields, append, remove } = useFieldArray({ control, name: 'items' });
  const items = useWatch({ control, name: 'items' }) || [];
  const calc = calculateDocument(items, { interstate, headerDiscount });
  const err = (i, f) => errors?.items?.[i]?.[f];

  const pickMaterial = (index, m) => {
    setValue(`items.${index}.material`, m.id, { shouldDirty: true });
    setValue(`items.${index}.description`, `${m.name} ${m.brand}`.trim());
    setValue(`items.${index}.unit`, m.unit);
    setValue(`items.${index}.hsn_code`, m.hsn_code);
    setValue(`items.${index}.gst_rate`, String(Number(m.gst_rate)));
    if (m[priceField] !== undefined)
      setValue(`items.${index}.rate`, m[priceField], { shouldDirty: true });
  };

  const num = (name, props = {}) => (
    <input
      type="number"
      step="any"
      min="0"
      inputMode="decimal"
      disabled={disabled}
      className={clsx('input px-2 text-right', props.invalid && 'border-red-500')}
      {...register(name)}
    />
  );

  return (
    <div>
      <div className="space-y-3">
        {fields.map((field, i) => {
          const isMaterial = items[i]?.item_type !== 'SERVICE';
          const line = calc.lines[i] || { total: 0, tax: 0 };
          return (
            <div
              key={field.id}
              className="rounded-xl border border-slate-200 p-3 dark:border-slate-700"
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {i + 1}. {isMaterial ? 'Material' : 'Service / labour'}
                </span>
                {!disabled && fields.length > 1 && (
                  <button
                    type="button"
                    className="btn-ghost py-1 text-red-600"
                    onClick={() => remove(i)}
                    aria-label={`Remove line ${i + 1}`}
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2 md:grid-cols-12">
                <div className="col-span-2 md:col-span-4">
                  <label className="label text-xs">{isMaterial ? 'Material' : 'Description'}</label>
                  {isMaterial ? (
                    <>
                      <MaterialPicker
                        value={items[i]?.material}
                        priceField={priceField}
                        invalid={!!err(i, 'material')}
                        onSelect={(m) => pickMaterial(i, m)}
                      />
                      <input type="hidden" {...register(`items.${i}.material`)} />
                    </>
                  ) : (
                    <input
                      className={clsx('input', err(i, 'description') && 'border-red-500')}
                      placeholder="e.g. Unloading charges"
                      disabled={disabled}
                      {...register(`items.${i}.description`)}
                    />
                  )}
                  {(err(i, 'material') || err(i, 'description')) && (
                    <p className="mt-1 text-xs text-red-600">
                      {(err(i, 'material') || err(i, 'description')).message}
                    </p>
                  )}
                </div>
                <div className="md:col-span-1">
                  <label className="label text-xs">HSN/SAC</label>
                  <input
                    className="input px-2"
                    disabled={disabled}
                    {...register(`items.${i}.hsn_code`)}
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="label text-xs">Qty</label>
                  {num(`items.${i}.quantity`, { invalid: !!err(i, 'quantity') })}
                  {err(i, 'quantity') && (
                    <p className="mt-1 text-xs text-red-600">{err(i, 'quantity').message}</p>
                  )}
                </div>
                <div className="md:col-span-1">
                  <label className="label text-xs">Unit</label>
                  <select
                    className="input px-1"
                    disabled={disabled}
                    {...register(`items.${i}.unit`)}
                  >
                    <option value="">—</option>
                    {units.map((u) => (
                      <option key={u.value} value={u.value}>
                        {u.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="label text-xs">Rate (₹)</label>
                  {num(`items.${i}.rate`, { invalid: !!err(i, 'rate') })}
                  {err(i, 'rate') && (
                    <p className="mt-1 text-xs text-red-600">{err(i, 'rate').message}</p>
                  )}
                </div>
                <div className="md:col-span-1">
                  <label className="label text-xs">Disc %</label>
                  {num(`items.${i}.discount_percent`)}
                </div>
                <div className="md:col-span-1">
                  <label className="label text-xs">GST %</label>
                  <select
                    className="input px-1"
                    disabled={disabled}
                    {...register(`items.${i}.gst_rate`)}
                  >
                    {GST_RATES.map((r) => (
                      <option key={r} value={r}>
                        {r}%
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap justify-end gap-x-4 text-xs text-slate-500">
                {line.discount > 0 && <span>Discount −{formatINR(line.discount)}</span>}
                <span>Taxable {formatINR(line.taxable)}</span>
                <span>
                  {interstate ? 'IGST' : 'CGST+SGST'} {formatINR(line.tax)}
                </span>
                <span className="font-semibold text-slate-800 dark:text-slate-100">
                  Line total {formatINR(line.total)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      {typeof errors?.items?.message === 'string' && (
        <p className="mt-2 text-sm text-red-600">{errors.items.message}</p>
      )}
      {!disabled && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => append(emptyMaterialLine())}
          >
            <Plus size={16} /> Add material
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => append(emptyServiceLine())}
          >
            <Wrench size={16} /> Add service / labour
          </button>
        </div>
      )}
    </div>
  );
}
