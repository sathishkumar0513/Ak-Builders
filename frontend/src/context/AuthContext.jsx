import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { SESSION_EXPIRED_EVENT, tokenStore } from '@/api/client';
import { authApi } from '@/api/services';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState(() => (tokenStore.getAccess() ? 'loading' : 'anonymous'));

  // Restore the session on page load
  useEffect(() => {
    if (status !== 'loading') return;
    let cancelled = false;
    authApi
      .me()
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setStatus('authenticated');
      })
      .catch(() => {
        if (cancelled) return;
        tokenStore.clear();
        setStatus('anonymous');
      });
    return () => {
      cancelled = true;
    };
  }, [status]);

  // Refresh token expired / revoked → back to login
  useEffect(() => {
    const onExpired = () => {
      setUser(null);
      setStatus('anonymous');
      queryClient.clear();
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [queryClient]);

  const login = useCallback(async (username, password) => {
    const data = await authApi.login(username, password);
    tokenStore.set(data);
    setUser(data.user);
    setStatus('authenticated');
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    const refresh = tokenStore.getRefresh();
    try {
      if (refresh) await authApi.logout(refresh);
    } catch {
      /* token may already be invalid — still log out locally */
    }
    tokenStore.clear();
    setUser(null);
    setStatus('anonymous');
    queryClient.clear();
  }, [queryClient]);

  /** After change-password the server returns a fresh token pair + user. */
  const applySession = useCallback((data) => {
    if (data.access) tokenStore.set(data);
    if (data.user) setUser(data.user);
  }, []);

  const hasRole = useCallback(
    (...roles) =>
      !!user && (user.role_code === 'SUPER_ADMIN' || roles.flat().includes(user.role_code)),
    [user],
  );

  const value = useMemo(
    () => ({
      user,
      status,
      isAuthenticated: status === 'authenticated',
      login,
      logout,
      applySession,
      setUser,
      hasRole,
    }),
    [user, status, login, logout, applySession, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
