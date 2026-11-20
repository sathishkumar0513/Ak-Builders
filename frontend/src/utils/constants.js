export const ROLES = {
  SUPER_ADMIN: 'SUPER_ADMIN',
  ADMIN: 'ADMIN',
  ACCOUNTANT: 'ACCOUNTANT',
  SITE_ENGINEER: 'SITE_ENGINEER',
  SALES: 'SALES',
};

export const PAYMENT_MODES = [
  { value: 'CASH', label: 'Cash' },
  { value: 'UPI', label: 'UPI' },
  { value: 'BANK', label: 'Bank Transfer' },
  { value: 'CHEQUE', label: 'Cheque' },
  { value: 'CARD', label: 'Card' },
];

export const UNITS = [
  'bag',
  'kg',
  'ton',
  'piece',
  'sqft',
  'cft',
  'load',
  'meter',
  'litre',
  'box',
  'nos',
  'ls',
  'day',
];

export const EXPENSE_CATEGORIES = [
  { value: 'LABOUR', label: 'Labour wages' },
  { value: 'TRANSPORT', label: 'Transport' },
  { value: 'SITE', label: 'Site expense' },
  { value: 'LOCAL_MAT', label: 'Local material purchase' },
  { value: 'EQUIPMENT', label: 'Equipment / tool hire' },
  { value: 'FUEL', label: 'Fuel' },
  { value: 'OFFICE', label: 'Office / rent' },
  { value: 'MISC', label: 'Miscellaneous' },
];
