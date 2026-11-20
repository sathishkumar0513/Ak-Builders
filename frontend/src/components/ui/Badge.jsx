import clsx from 'clsx';

const COLORS = {
  gray: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
  green: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
  red: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  amber: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  blue: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  purple: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
  orange: 'bg-brand-100 text-brand-800 dark:bg-brand-900/40 dark:text-brand-300',
};

export default function Badge({ color = 'gray', children, className }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        COLORS[color],
        className,
      )}
    >
      {children}
    </span>
  );
}
