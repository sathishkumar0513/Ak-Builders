import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronDown, KeyRound, LogOut, Menu, Moon, Sun, User } from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useAuth } from '@/context/AuthContext';
import { useClickOutside } from '@/hooks/useClickOutside';

export default function Topbar({ onMenu }) {
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useClickOutside(ref, () => setOpen(false), open);

  const initials = (user?.full_name || user?.username || '?')
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  const onLogout = async () => {
    setOpen(false);
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur dark:border-slate-700 dark:bg-slate-800/90">
      <button className="lg:hidden" onClick={onMenu} aria-label="Open menu">
        <Menu size={22} />
      </button>
      <div className="flex-1" />
      <button
        onClick={toggle}
        className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-700"
        aria-label="Toggle theme"
      >
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </button>
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 rounded-lg p-1 pr-2 hover:bg-slate-100 dark:hover:bg-slate-700"
          aria-haspopup="menu"
          aria-expanded={open}
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
            {initials}
          </span>
          <span className="hidden text-left sm:block">
            <span className="block text-sm font-medium leading-tight">{user?.full_name}</span>
            <span className="block text-xs text-slate-500">{user?.role_name}</span>
          </span>
          <ChevronDown size={16} className="text-slate-400" />
        </button>
        {open && (
          <div
            role="menu"
            className="absolute right-0 mt-2 w-52 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800"
          >
            <div className="border-b border-slate-100 px-4 py-2 dark:border-slate-700 sm:hidden">
              <p className="text-sm font-medium">{user?.full_name}</p>
              <p className="text-xs text-slate-500">{user?.role_name}</p>
            </div>
            <Link
              to="/profile"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700"
            >
              <User size={16} /> My profile
            </Link>
            <Link
              to="/change-password"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700"
            >
              <KeyRound size={16} /> Change password
            </Link>
            <button
              onClick={onLogout}
              className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
            >
              <LogOut size={16} /> Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
