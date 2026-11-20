import { useState } from 'react';
import clsx from 'clsx';
import { useAuth } from '@/context/AuthContext';
import PageHeader from '@/components/ui/PageHeader';
import CompanyProfileForm from './CompanyProfileForm';
import NumberSeries from './NumberSeries';
import TermsTemplates from './TermsTemplates';

export default function SettingsPage() {
  const { hasRole } = useAuth();
  const [tab, setTab] = useState('company');
  const tabs = [
    { id: 'company', label: 'Company profile' },
    { id: 'series', label: 'Document numbers' },
    { id: 'terms', label: 'Terms & conditions' },
  ];
  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Company details printed on quotations, invoices and receipts"
      />
      <div className="mb-4 flex gap-1 border-b border-slate-200 dark:border-slate-700">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              '-mb-px border-b-2 px-4 py-2 text-sm font-medium',
              tab === t.id
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-700',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'company' && <CompanyProfileForm />}
      {tab === 'series' && <NumberSeries canEdit={hasRole('SUPER_ADMIN')} />}
      {tab === 'terms' && <TermsTemplates canEdit={hasRole('ADMIN')} />}
    </>
  );
}
