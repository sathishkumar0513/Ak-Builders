import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import FullPageLoader from '@/components/ui/FullPageLoader';
import AppLayout from '@/layouts/AppLayout';
import { GuestRoute, ProtectedRoute, RoleRoute } from './guards';
import { rolesFor } from '@/config/navigation';
import Dashboard from '@/pages/Dashboard';
import NotFound from '@/pages/NotFound';
import Login from '@/pages/auth/Login';
const ForgotPassword = lazy(() => import('@/pages/auth/ForgotPassword'));
const ResetPassword = lazy(() => import('@/pages/auth/ResetPassword'));
const ChangePassword = lazy(() => import('@/pages/auth/ChangePassword'));
const Profile = lazy(() => import('@/pages/Profile'));
const UsersPage = lazy(() => import('@/pages/users/UsersPage'));
const AuditLogPage = lazy(() => import('@/pages/audit/AuditLogPage'));
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage'));
const CustomersPage = lazy(() => import('@/pages/customers/CustomersPage'));
const CustomerDetailPage = lazy(() => import('@/pages/customers/CustomerDetailPage'));
const MaterialsPage = lazy(() => import('@/pages/materials/MaterialsPage'));
const MaterialDetailPage = lazy(() => import('@/pages/materials/MaterialDetailPage'));
const SuppliersPage = lazy(() => import('@/pages/suppliers/SuppliersPage'));
const SupplierDetailPage = lazy(() => import('@/pages/suppliers/SupplierDetailPage'));
const PurchasesPage = lazy(() => import('@/pages/purchases/PurchasesPage'));
const PurchaseFormPage = lazy(() => import('@/pages/purchases/PurchaseFormPage'));
const PurchaseDetailPage = lazy(() => import('@/pages/purchases/PurchaseDetailPage'));
const QuotationsPage = lazy(() => import('@/pages/quotations/QuotationsPage'));
const QuotationFormPage = lazy(() => import('@/pages/quotations/QuotationFormPage'));
const QuotationDetailPage = lazy(() => import('@/pages/quotations/QuotationDetailPage'));
const ProjectsPage = lazy(() => import('@/pages/projects/ProjectsPage'));
const ProjectDetailPage = lazy(() => import('@/pages/projects/ProjectDetailPage'));
const InvoicesPage = lazy(() => import('@/pages/invoices/InvoicesPage'));
const InvoiceFormPage = lazy(() => import('@/pages/invoices/InvoiceFormPage'));
const InvoiceDetailPage = lazy(() => import('@/pages/invoices/InvoiceDetailPage'));
const PaymentsPage = lazy(() => import('@/pages/payments/PaymentsPage'));
const AdvancesPage = lazy(() => import('@/pages/advances/AdvancesPage'));
const AdvanceDetailPage = lazy(() => import('@/pages/advances/AdvanceDetailPage'));

const ExpensesPage = lazy(() => import('@/pages/expenses/ExpensesPage'));
const ReportsPage = lazy(() => import('@/pages/reports/ReportsPage'));
const ReportViewPage = lazy(() => import('@/pages/reports/ReportViewPage'));

export default function AppRoutes() {
  return (
    <Suspense fallback={<FullPageLoader />}>
      <Routes>
        <Route element={<GuestRoute />}>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
        </Route>
        <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="profile" element={<Profile />} />
            <Route path="change-password" element={<ChangePassword />} />

            <Route element={<RoleRoute roles={rolesFor('/users')} />}>
              <Route path="users" element={<UsersPage />} />
              <Route path="audit-log" element={<AuditLogPage />} />
            </Route>
            <Route element={<RoleRoute roles={rolesFor('/customers')} />}>
              <Route path="customers" element={<CustomersPage />} />
              <Route path="customers/:id" element={<CustomerDetailPage />} />
            </Route>
            <Route element={<RoleRoute roles={rolesFor('/materials')} />}>
              <Route path="materials" element={<MaterialsPage />} />
              <Route path="materials/:id" element={<MaterialDetailPage />} />
            </Route>
            <Route element={<RoleRoute roles={rolesFor('/suppliers')} />}>
              <Route path="suppliers" element={<SuppliersPage />} />
              <Route path="suppliers/:id" element={<SupplierDetailPage />} />
              <Route path="purchases" element={<PurchasesPage />} />
              <Route path="purchases/new" element={<PurchaseFormPage />} />
              <Route path="purchases/:id" element={<PurchaseDetailPage />} />
              <Route path="purchases/:id/edit" element={<PurchaseFormPage />} />
            </Route>
            <Route element={<RoleRoute roles={rolesFor('/quotations')} />}>
              <Route path="quotations" element={<QuotationsPage />} />
              <Route path="quotations/new" element={<QuotationFormPage />} />
              <Route path="quotations/:id" element={<QuotationDetailPage />} />
              <Route path="quotations/:id/edit" element={<QuotationFormPage />} />
            </Route>
            <Route element={<RoleRoute roles={rolesFor('/projects')} />}>
              <Route path="projects" element={<ProjectsPage />} />
              <Route path="projects/:id" element={<ProjectDetailPage />} />
            </Route>
            <Route element={<RoleRoute roles={rolesFor('/invoices')} />}>
              <Route path="invoices" element={<InvoicesPage />} />
              <Route path="invoices/new" element={<InvoiceFormPage />} />
              <Route path="invoices/:id" element={<InvoiceDetailPage />} />
              <Route path="invoices/:id/edit" element={<InvoiceFormPage />} />
              <Route path="payments" element={<PaymentsPage />} />
              <Route path="advances" element={<AdvancesPage />} />
              <Route path="advances/:id" element={<AdvanceDetailPage />} />
            </Route>
            <Route element={<RoleRoute roles={rolesFor('/settings')} />}>
              <Route path="settings" element={<SettingsPage />} />
            </Route>

            <Route element={<RoleRoute roles={rolesFor('/expenses')} />}>
              <Route path="expenses" element={<ExpensesPage />} />
            </Route>
            <Route element={<RoleRoute roles={rolesFor('/reports')} />}>
              <Route path="reports" element={<ReportsPage />} />
              <Route path="reports/:key" element={<ReportViewPage />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
