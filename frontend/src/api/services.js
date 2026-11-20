import { api } from './client';

/** Thin wrappers around the REST API — one place to change URLs. */
export const authApi = {
  login: (username, password) =>
    api.post('/auth/login/', { username, password }).then((r) => r.data),
  logout: (refresh) => api.post('/auth/logout/', { refresh }),
  me: () => api.get('/auth/me/').then((r) => r.data),
  updateMe: (data) => api.patch('/auth/me/', data).then((r) => r.data),
  changePassword: (data) => api.post('/auth/change-password/', data).then((r) => r.data),
  forgotPassword: (email) => api.post('/auth/forgot-password/', { email }).then((r) => r.data),
  resetPassword: (data) => api.post('/auth/reset-password/', data).then((r) => r.data),
};

export const usersApi = {
  list: (params) => api.get('/users/', { params }).then((r) => r.data),
  create: (data) => api.post('/users/', data).then((r) => r.data),
  update: (id, data) => api.patch(`/users/${id}/`, data).then((r) => r.data),
  remove: (id) => api.delete(`/users/${id}/`),
  activate: (id) => api.post(`/users/${id}/activate/`).then((r) => r.data),
  deactivate: (id) => api.post(`/users/${id}/deactivate/`).then((r) => r.data),
  resetPassword: (id, newPassword) =>
    api.post(`/users/${id}/reset-password/`, { new_password: newPassword }).then((r) => r.data),
  roles: () => api.get('/roles/').then((r) => r.data),
};

export const auditApi = {
  list: (params) => api.get('/audit-logs/', { params }).then((r) => r.data),
};

export const settingsApi = {
  company: () => api.get('/settings/company/').then((r) => r.data),
  updateCompany: (data) =>
    api
      .patch('/settings/company/', data, {
        headers: data instanceof FormData ? { 'Content-Type': 'multipart/form-data' } : undefined,
      })
      .then((r) => r.data),
  sequences: () => api.get('/settings/sequences/').then((r) => r.data),
  updateSequence: (id, data) => api.patch(`/settings/sequences/${id}/`, data).then((r) => r.data),
  lookups: () => api.get('/lookups/').then((r) => r.data),
  cities: (state) => api.get('/lookups/cities/', { params: { state } }).then((r) => r.data),
};

/** Generic REST resource helper: list / get / create / update / remove + custom actions. */
function resource(base) {
  return {
    list: (params) => api.get(`/${base}/`, { params }).then((r) => r.data),
    get: (id) => api.get(`/${base}/${id}/`).then((r) => r.data),
    create: (data) => api.post(`/${base}/`, data).then((r) => r.data),
    update: (id, data) => api.patch(`/${base}/${id}/`, data).then((r) => r.data),
    remove: (id) => api.delete(`/${base}/${id}/`),
    restore: (id) => api.post(`/${base}/${id}/restore/`).then((r) => r.data),
    action: (id, name, data) => api.post(`/${base}/${id}/${name}/`, data).then((r) => r.data),
    detail: (id, name, params) =>
      api.get(`/${base}/${id}/${name}/`, { params }).then((r) => r.data),
    collection: (name, params) => api.get(`/${base}/${name}/`, { params }).then((r) => r.data),
  };
}

export const customersApi = resource('customers');
export const materialsApi = resource('materials');
export const categoriesApi = resource('material-categories');
export const stockMovementsApi = resource('stock-movements');
export const suppliersApi = resource('suppliers');
export const purchasesApi = resource('purchases');
export const supplierPaymentsApi = resource('supplier-payments');
export const quotationsApi = resource('quotations');
export const termsApi = resource('settings/terms');
export const projectsApi = resource('projects');
usersApi.lookup = (params) => api.get('/users/lookup/', { params }).then((r) => r.data);
export const invoicesApi = resource('invoices');
export const advancesApi = resource('advances');
export const paymentsApi = resource('payments');
export const adjustmentsApi = resource('advance-adjustments');
export const expensesApi = resource('expenses');

export const dashboardApi = {
  get: () => api.get('/dashboard/').then((r) => r.data),
};

export const reportsApi = {
  list: () => api.get('/reports/').then((r) => r.data),
  run: (key, params) => api.get(`/reports/${key}/`, { params }).then((r) => r.data),
  /** Excel / PDF download as a Blob plus the server's file name. */
  file: async (key, params, ext) => {
    const r = await api.get(`/reports/${key}/`, {
      params: { ...params, export: ext },
      responseType: 'blob',
    });
    const cd = r.headers['content-disposition'] || '';
    const name = /filename="([^"]+)"/.exec(cd)?.[1] || `${key}.${ext}`;
    return { blob: r.data, name };
  },
};
