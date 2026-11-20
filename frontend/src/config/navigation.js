import {
  LayoutDashboard,
  Users,
  Package,
  Truck,
  FileText,
  HardHat,
  Wallet,
  IndianRupee,
  Receipt,
  Wallet2,
  BarChart3,
  Settings,
  UserCog,
  HistoryIcon,
  ShoppingCart,
} from 'lucide-react';
import { ROLES } from '@/utils/constants';

const { SUPER_ADMIN, ADMIN, ACCOUNTANT, SITE_ENGINEER, SALES } = ROLES;
const ALL = [SUPER_ADMIN, ADMIN, ACCOUNTANT, SITE_ENGINEER, SALES];

/** Sidebar menu. `roles` decides who sees each item (enforced again on the API in Phase 2). */
export const NAV_ITEMS = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard, roles: ALL },
  {
    label: 'Customers',
    path: '/customers',
    icon: Users,
    roles: [SUPER_ADMIN, ADMIN, ACCOUNTANT, SALES],
  },
  { label: 'Materials', path: '/materials', icon: Package, roles: ALL },
  { label: 'Suppliers', path: '/suppliers', icon: Truck, roles: [SUPER_ADMIN, ADMIN, ACCOUNTANT] },
  {
    label: 'Purchases',
    path: '/purchases',
    icon: ShoppingCart,
    roles: [SUPER_ADMIN, ADMIN, ACCOUNTANT],
  },
  {
    label: 'Quotations',
    path: '/quotations',
    icon: FileText,
    roles: [SUPER_ADMIN, ADMIN, ACCOUNTANT, SALES],
  },
  { label: 'Projects & Sites', path: '/projects', icon: HardHat, roles: ALL },
  { label: 'Advances', path: '/advances', icon: Wallet, roles: [SUPER_ADMIN, ADMIN, ACCOUNTANT] },
  {
    label: 'Payments',
    path: '/payments',
    icon: IndianRupee,
    roles: [SUPER_ADMIN, ADMIN, ACCOUNTANT],
  },
  { label: 'Invoices', path: '/invoices', icon: Receipt, roles: [SUPER_ADMIN, ADMIN, ACCOUNTANT] },
  {
    label: 'Expenses',
    path: '/expenses',
    icon: Wallet2,
    roles: [SUPER_ADMIN, ADMIN, ACCOUNTANT, SITE_ENGINEER],
  },
  { label: 'Reports', path: '/reports', icon: BarChart3, roles: [SUPER_ADMIN, ADMIN, ACCOUNTANT] },
  { label: 'Users', path: '/users', icon: UserCog, roles: [SUPER_ADMIN, ADMIN] },
  { label: 'Audit Log', path: '/audit-log', icon: HistoryIcon, roles: [SUPER_ADMIN, ADMIN] },
  { label: 'Settings', path: '/settings', icon: Settings, roles: [SUPER_ADMIN, ADMIN] },
];

export function navForRole(role) {
  if (!role) return [];
  if (role === SUPER_ADMIN) return NAV_ITEMS;
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}

/** Roles allowed for a path — used by <RoleRoute> so the menu and the routes never disagree. */
export const rolesFor = (path) => NAV_ITEMS.find((i) => i.path === path)?.roles || ALL;
