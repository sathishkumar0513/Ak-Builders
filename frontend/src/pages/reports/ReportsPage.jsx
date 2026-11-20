import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  BarChart3,
  BookOpen,
  Boxes,
  ChevronRight,
  Clock,
  FileSpreadsheet,
  HardHat,
  IndianRupee,
  Percent,
  ShoppingCart,
  Users,
  Wallet2,
} from 'lucide-react';
import { reportsApi } from '@/api/services';
import PageHeader from '@/components/ui/PageHeader';

const ICONS = {
  payments: IndianRupee,
  outstanding: Clock,
  'customer-outstanding': Users,
  ledger: BookOpen,
  'sales-register': FileSpreadsheet,
  quotations: Percent,
  'project-pl': HardHat,
  expenses: Wallet2,
  stock: Boxes,
  purchases: ShoppingCart,
};

export default function ReportsPage() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['reports', 'list'],
    queryFn: reportsApi.list,
    staleTime: Infinity,
  });
  const groups = data.reduce((acc, r) => {
    (acc[r.group] ||= []).push(r);
    return acc;
  }, {});

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Every report can be filtered by date and downloaded as Excel or PDF"
      />
      {isLoading && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card h-24 animate-pulse" />
          ))}
        </div>
      )}
      <div className="space-y-6">
        {Object.entries(groups).map(([group, items]) => (
          <section key={group}>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
              {group}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((r) => {
                const Icon = ICONS[r.key] || BarChart3;
                return (
                  <Link
                    key={r.key}
                    to={`/reports/${r.key}`}
                    className="card group flex items-start gap-3 transition hover:border-brand-300"
                  >
                    <div className="rounded-lg bg-brand-50 p-2 text-brand-600 dark:bg-brand-900/30">
                      <Icon size={20} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium group-hover:text-brand-700">{r.title}</p>
                      <p className="text-sm text-slate-500">{r.description}</p>
                    </div>
                    <ChevronRight size={18} className="mt-1 shrink-0 text-slate-400" />
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
