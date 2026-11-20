/** Badge colours per status, shared by list and detail pages. */
export const PURCHASE_STATUS = {
  ORDERED: 'blue',
  PARTIAL: 'amber',
  RECEIVED: 'green',
  CANCELLED: 'red',
};
export const PAYMENT_STATUS = { UNPAID: 'red', PARTIAL: 'amber', PAID: 'green' };
export const MOVEMENT_COLOR = {
  PURCHASE_IN: 'green',
  SITE_RETURN: 'green',
  ADJUST_IN: 'blue',
  OPENING: 'gray',
  SITE_ISSUE: 'orange',
  SALE_OUT: 'orange',
  ADJUST_OUT: 'red',
};
export const INWARD = new Set(['PURCHASE_IN', 'SITE_RETURN', 'ADJUST_IN', 'OPENING']);
export const QUOTATION_STATUS = {
  DRAFT: 'gray',
  SENT: 'blue',
  APPROVED: 'green',
  REJECTED: 'red',
  EXPIRED: 'amber',
  CONVERTED: 'purple',
};
export const INVOICE_STATUS = { UNPAID: 'red', PARTIAL: 'amber', PAID: 'green', CANCELLED: 'gray' };
export const ADVANCE_STATUS = {
  OPEN: 'blue',
  PARTIAL: 'amber',
  ADJUSTED: 'green',
  REFUNDED: 'gray',
};
export const PROJECT_STATUS = {
  PLANNED: 'blue',
  IN_PROGRESS: 'orange',
  ON_HOLD: 'amber',
  COMPLETED: 'green',
  CANCELLED: 'gray',
};
export const STAGE_STATUS = { PENDING: 'gray', DUE: 'red', PARTIAL: 'amber', PAID: 'green' };
export const CHEQUE_STATUS = { NA: null, PENDING: 'amber', CLEARED: 'green', BOUNCED: 'red' };
