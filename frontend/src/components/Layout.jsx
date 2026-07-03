import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "📊", end: true },
  { to: "/transactions", label: "Tranzaksiyalar", icon: "🧾" },
  { to: "/debts", label: "Qarzlar", icon: "💳" },
];

export default function Layout() {
  const { user, companies, activeCompany, selectCompany, logout } = useAuth();
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <div style={styles.shell}>
      <header style={styles.topbar}>
        <div>
          <div style={styles.greeting}>Salom, {user?.full_name?.split(" ")[0] || "foydalanuvchi"} 👋</div>
          <button style={styles.companySwitcher} onClick={() => setSwitcherOpen((v) => !v)}>
            🏢 {activeCompany?.name || "Kompaniya tanlanmagan"} <span style={{ opacity: 0.6 }}>▾</span>
          </button>
        </div>
        <button
          style={styles.logoutBtn}
          onClick={() => {
            logout();
            navigate("/login", { replace: true });
          }}
          title="Chiqish"
        >
          ⎋
        </button>
      </header>

      {switcherOpen && (
        <div style={styles.switcherPanel}>
          {companies.map((c) => (
            <button
              key={c.id}
              style={{
                ...styles.switcherItem,
                ...(c.id === activeCompany?.id ? styles.switcherItemActive : {}),
              }}
              onClick={() => {
                selectCompany(c.id);
                setSwitcherOpen(false);
              }}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}

      <main style={styles.content}>
        <Outlet />
      </main>

      <nav style={styles.bottomNav}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            style={({ isActive }) => ({
              ...styles.navItem,
              color: isActive ? "var(--accent)" : "var(--ink-muted)",
            })}
          >
            <span style={{ fontSize: 20 }}>{item.icon}</span>
            <span style={{ fontSize: "var(--text-xs)" }}>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

const styles = {
  shell: {
    maxWidth: "var(--max-width)",
    margin: "0 auto",
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    position: "relative",
  },
  topbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    padding: "var(--space-5) var(--space-4) var(--space-3)",
  },
  greeting: { fontSize: "var(--text-sm)", color: "var(--ink-muted)" },
  companySwitcher: {
    marginTop: "var(--space-1)",
    fontSize: "var(--text-lg)",
    fontWeight: 700,
    color: "var(--ink)",
  },
  logoutBtn: {
    fontSize: "var(--text-lg)",
    color: "var(--ink-muted)",
    padding: "var(--space-2)",
  },
  switcherPanel: {
    margin: "0 var(--space-4) var(--space-3)",
    background: "var(--bg-elevated)",
    border: "1px solid var(--line)",
    borderRadius: "var(--radius-md)",
    overflow: "hidden",
  },
  switcherItem: {
    display: "block",
    width: "100%",
    textAlign: "left",
    padding: "var(--space-3) var(--space-4)",
    fontSize: "var(--text-sm)",
    borderBottom: "1px solid var(--line)",
  },
  switcherItemActive: { color: "var(--accent)", fontWeight: 700 },
  content: {
    flex: 1,
    padding: "0 var(--space-4) var(--space-8)",
  },
  bottomNav: {
    position: "sticky",
    bottom: 0,
    display: "flex",
    background: "var(--bg-elevated)",
    borderTop: "1px solid var(--line)",
  },
  navItem: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 2,
    padding: "var(--space-3) 0",
  },
};
