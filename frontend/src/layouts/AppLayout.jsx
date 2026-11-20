import { Suspense, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from '@/components/layout/Sidebar';
import Topbar from '@/components/layout/Topbar';
import Breadcrumbs from '@/components/layout/Breadcrumbs';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import { useAuth } from '@/context/AuthContext';

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  const { pathname } = useLocation();
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar open={open} onClose={() => setOpen(false)} role={user?.role_code} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Breadcrumbs />
          <ErrorBoundary key={pathname}>
            <Suspense fallback={<div className="card h-48 animate-pulse" />}>
              <Outlet />
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
