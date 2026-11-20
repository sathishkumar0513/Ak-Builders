import { Link } from 'react-router-dom';
import { ShieldX } from 'lucide-react';

export default function Forbidden() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <ShieldX size={48} className="text-red-500" />
      <p className="text-xl font-semibold">Access denied</p>
      <p className="max-w-sm text-sm text-slate-500">
        Your role does not have access to this page. Ask an Admin if you need it.
      </p>
      <Link to="/" className="btn-primary">
        Back to dashboard
      </Link>
    </div>
  );
}
