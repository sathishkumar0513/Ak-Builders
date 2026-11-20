import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import FullPageLoader from '@/components/ui/FullPageLoader';
import Forbidden from '@/pages/Forbidden';

/** Logged-in users only. Forces a password change when the account has a temporary password. */
export function ProtectedRoute() {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <FullPageLoader />;
  if (status !== 'authenticated')
    return <Navigate to="/login" replace state={{ from: location }} />;
  if (user?.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />;
  }
  return <Outlet />;
}

/** Only for the given roles (Super Admin always passes). The API enforces the same rule. */
export function RoleRoute({ roles }) {
  const { hasRole } = useAuth();
  return hasRole(roles) ? <Outlet /> : <Forbidden />;
}

/** Login / forgot-password pages: skip them if already logged in. */
export function GuestRoute() {
  const { status } = useAuth();
  if (status === 'loading') return <FullPageLoader />;
  return status === 'authenticated' ? <Navigate to="/" replace /> : <Outlet />;
}
