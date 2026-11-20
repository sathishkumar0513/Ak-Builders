import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export default function BackLink({ to, children }) {
  return (
    <Link
      to={to}
      className="mb-2 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600"
    >
      <ArrowLeft size={14} /> {children}
    </Link>
  );
}
