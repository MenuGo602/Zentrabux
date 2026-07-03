/**
 * Zentra API klienti.
 *
 * Bot'dagi app/bot/api_client.py bilan bir xil g'oya: access token muddati
 * o'tsa (401), refresh token bilan avtomatik yangilaymiz va so'rovni bir
 * marta qayta uramiz. Tokenlar localStorage'da saqlanadi.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_PREFIX = "/api/v1";

const TOKEN_KEY = "zentra.tokens";

export class APIError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

export function getStoredTokens() {
  const raw = localStorage.getItem(TOKEN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    localStorage.removeItem(TOKEN_KEY);
    return null;
  }
}

export function storeTokens(tokens) {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
}

async function rawRequest(path, { method = "GET", body, token, params } = {}) {
  const url = new URL(`${API_BASE_URL}${API_PREFIX}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
  }

  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  return response;
}

async function refreshTokens() {
  const tokens = getStoredTokens();
  if (!tokens?.refresh_token) throw new APIError(401, "Sessiya yo'q");

  const response = await rawRequest("/auth/refresh", {
    method: "POST",
    body: { refresh_token: tokens.refresh_token },
  });

  if (!response.ok) {
    clearTokens();
    throw new APIError(response.status, "Sessiya muddati tugagan");
  }

  const newTokens = await response.json();
  storeTokens(newTokens);
  return newTokens;
}

/**
 * Asosiy so'rov funksiyasi — token talab qiladigan barcha endpointlar shu orqali chaqiriladi.
 * 401 kelsa: bitta marta refresh qilib qayta uradi.
 */
export async function request(path, options = {}) {
  let tokens = getStoredTokens();
  if (!tokens?.access_token) {
    throw new APIError(401, "Kirilmagan — /login sahifasiga o'ting");
  }

  let response = await rawRequest(path, { ...options, token: tokens.access_token });

  if (response.status === 401) {
    tokens = await refreshTokens();
    response = await rawRequest(path, { ...options, token: tokens.access_token });
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errBody = await response.json();
      detail = errBody.detail || detail;
    } catch {
      /* javob JSON emas — statusText bilan qolamiz */
    }
    throw new APIError(response.status, detail);
  }

  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response.blob(); // PDF/Excel
}

/** Autentifikatsiyasiz so'rov (login, register, widget auth uchun). */
export async function publicRequest(path, options = {}) {
  const response = await rawRequest(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errBody = await response.json();
      detail = errBody.detail || detail;
    } catch {
      /* noop */
    }
    throw new APIError(response.status, detail);
  }
  return response.json();
}

// ─── Qulaylik metodlari ──────────────────────────────────────────────────
export const api = {
  // Auth
  loginWithTelegramWidget: (widgetData) =>
    publicRequest("/auth/telegram-widget", { method: "POST", body: widgetData }),
  me: () => request("/auth/me"),

  // Companies
  listCompanies: () => request("/companies"),
  createCompany: (body) => request("/companies", { method: "POST", body }),

  // Dashboard / Reports
  dashboard: (companyId, periodStart, periodEnd) =>
    request(`/reports/${companyId}/dashboard`, {
      params: { period_start: periodStart, period_end: periodEnd },
    }),

  // Transactions
  listTransactions: (companyId, limit = 20) =>
    request(`/transactions/${companyId}`, { params: { limit } }),
  confirmTransaction: (companyId, txId) =>
    request(`/transactions/${companyId}/${txId}/confirm`, { method: "PATCH" }),

  // Debts
  listDebts: (companyId, overdueOnly = false) =>
    request(overdueOnly ? `/debts/${companyId}/overdue` : `/debts/${companyId}`),
  debtsAging: (companyId) => request(`/debts/${companyId}/aging`),
  createDebt: (companyId, body) => request(`/debts/${companyId}`, { method: "POST", body }),

  // Customers / Suppliers
  listCustomers: (companyId, search) =>
    request(`/customers/${companyId}`, { params: { search } }),
  createCustomer: (companyId, body) => request(`/customers/${companyId}`, { method: "POST", body }),
  listSuppliers: (companyId, search) =>
    request(`/suppliers/${companyId}`, { params: { search } }),
  createSupplier: (companyId, body) => request(`/suppliers/${companyId}`, { method: "POST", body }),

  // Tax
  upcomingTaxDeadlines: (daysAhead = 30) =>
    request("/tax/calendar/upcoming", { params: { days_ahead: daysAhead } }),
};
