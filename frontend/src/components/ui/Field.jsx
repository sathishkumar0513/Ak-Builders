import { forwardRef } from 'react';
import clsx from 'clsx';

/** Label + control + error text. Works with react-hook-form's register(). */
export function Field({ label, error, hint, required, children, className }) {
  return (
    <div className={className}>
      {label && (
        <label className="label">
          {label}
          {required && <span className="text-red-600"> *</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="mt-1 text-xs text-red-600">{error.message || error}</p>
      ) : (
        hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>
      )}
    </div>
  );
}

export const Input = forwardRef(function Input({ className, invalid, ...props }, ref) {
  return (
    <input ref={ref} className={clsx('input', invalid && 'border-red-500', className)} {...props} />
  );
});

export const Select = forwardRef(function Select(
  { className, invalid, options = [], placeholder, ...props },
  ref,
) {
  return (
    <select ref={ref} className={clsx('input', invalid && 'border-red-500', className)} {...props}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
});

export const Textarea = forwardRef(function Textarea({ className, invalid, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={clsx('input min-h-[80px]', invalid && 'border-red-500', className)}
      {...props}
    />
  );
});
