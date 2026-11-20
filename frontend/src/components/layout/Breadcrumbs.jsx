import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

const SPECIAL = {
  'project-pl': 'Project profit / loss',
  'sales-register': 'Sales register',
  'customer-outstanding': 'Customer outstanding',
  outstanding: 'Outstanding & ageing',
  quotations: 'Quotations',
  stock: 'Stock summary',
  purchases: 'Purchases',
  payments: 'Payments',
};
const toTitle = (s, parent) =>
  /^\d+$/.test(s)
    ? 'Details'
    : (parent === 'reports' && SPECIAL[s]) ||
      s.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export default function Breadcrumbs() {
  const parts = useLocation().pathname.split('/').filter(Boolean);
  if (!parts.length) return null;
  return (
    <nav className="mb-4 flex items-center gap-1 text-sm text-slate-500" aria-label="Breadcrumb">
      <Link to="/" className="hover:text-brand-600">
        <Home size={15} />
      </Link>
      {parts.map((p, i) => (
        <span key={p + i} className="flex items-center gap-1">
          <ChevronRight size={14} />
          {i === parts.length - 1 ? (
            <span className="font-medium text-slate-700 dark:text-slate-200">
              {toTitle(p, parts[i - 1])}
            </span>
          ) : (
            <Link to={`/${parts.slice(0, i + 1).join('/')}`} className="hover:text-brand-600">
              {toTitle(p, parts[i - 1])}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}
