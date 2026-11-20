import { NavLink } from 'react-router-dom';
import clsx from 'clsx';
import { X } from 'lucide-react';
import { navForRole } from '@/config/navigation';

export default function Sidebar({ open, onClose, role }) {
  const items = navForRole(role);
  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={clsx('fixed inset-0 z-30 bg-black/40 lg:hidden', open ? 'block' : 'hidden')}
        onClick={onClose}
      />
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-slate-900 text-slate-200 transition-transform lg:static lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-slate-800 px-4">
          <div className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="h-8 w-8" />
            <div>
              <p className="text-sm font-bold leading-tight text-white">AK Builders</p>
              <p className="text-[11px] text-slate-400">Management System</p>
            </div>
          </div>
          <button className="lg:hidden" onClick={onClose} aria-label="Close menu">
            <X size={20} />
          </button>
        </div>
        <nav className="no-scrollbar flex-1 space-y-1 overflow-y-auto p-3">
          {items.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition',
                  isActive
                    ? 'bg-brand-600 text-white'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white',
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <p className="border-t border-slate-800 p-3 text-center text-[11px] text-slate-500">
          v1.0 · Phase 6
        </p>
      </aside>
    </>
  );
}
