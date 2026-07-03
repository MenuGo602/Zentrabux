import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, APIError, clearTokens, getStoredTokens, storeTokens } from "../lib/apiClient";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [activeCompanyId, setActiveCompanyId] = useState(
    () => localStorage.getItem("zentra.activeCompany") || null
  );
  const [status, setStatus] = useState("loading"); // loading | authenticated | anonymous

  const loadSession = useCallback(async () => {
    const tokens = getStoredTokens();
    if (!tokens?.access_token) {
      setStatus("anonymous");
      return;
    }
    try {
      const [me, companyList] = await Promise.all([api.me(), api.listCompanies()]);
      setUser(me);
      setCompanies(companyList);
      if (!activeCompanyId && companyList.length > 0) {
        setActiveCompanyId(companyList[0].id);
      }
      setStatus("authenticated");
    } catch (e) {
      if (e instanceof APIError && e.status === 401) {
        clearTokens();
      }
      setStatus("anonymous");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const loginWithTelegramWidget = useCallback(
    async (widgetData) => {
      const tokens = await api.loginWithTelegramWidget(widgetData);
      storeTokens(tokens);
      await loadSession();
    },
    [loadSession]
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setCompanies([]);
    setStatus("anonymous");
  }, []);

  const selectCompany = useCallback((companyId) => {
    setActiveCompanyId(companyId);
    localStorage.setItem("zentra.activeCompany", companyId);
  }, []);

  const refreshCompanies = useCallback(async () => {
    const list = await api.listCompanies();
    setCompanies(list);
    return list;
  }, []);

  const activeCompany = companies.find((c) => c.id === activeCompanyId) || null;

  return (
    <AuthContext.Provider
      value={{
        user,
        companies,
        activeCompany,
        activeCompanyId,
        status,
        loginWithTelegramWidget,
        logout,
        selectCompany,
        refreshCompanies,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth AuthProvider ichida ishlatilishi kerak");
  return ctx;
}
