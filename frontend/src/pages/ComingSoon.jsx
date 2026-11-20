import { Construction } from 'lucide-react';

export default function ComingSoon({ title, phase }) {
  return (
    <div className="card flex flex-col items-center justify-center gap-3 py-16 text-center">
      <Construction size={40} className="text-brand-500" />
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="text-sm text-slate-500">This module is built in Phase {phase}.</p>
    </div>
  );
}
