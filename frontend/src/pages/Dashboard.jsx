import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, APIError } from "../lib/apiClient";
import { formatMoney, formatPercent, periodBounds } from "../lib/format";
import PeriodTabs from "../components/PeriodTabs";
import StatCard from "../components/StatCard";
import BalanceBeam from "../components/BalanceBeam";

export default function Dashboard() {
  const { activeCompanyId } = useAuth();
  const [period, setPeriod] = useState("month");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!activeCompanyId) return;
    setLoading(true);
    setError(null);

    const { start, end } = periodBounds(period);
    api
      .dashboard(activeCompanyId, start, end)
      .then(setData)
      .catch((e) => setError(e instanceof APIError ? e.detail : "Ma'lumot yuklanmadi"))
      .finally(() => setLoading(false));
  }, [activeCompanyId, period]);

  if (!activeCompanyId) {
    return <EmptyState text="Avval kompaniya tanlang yoki yarating." />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <PeriodTabs value={period} onChange={setPeriod} />

      {loading && <SkeletonHero />}
      {error && <ErrorBanner text={error} />}

      {data && !loading && (
        <>
          <div style={styles.hero}>
            <div style={styles.heroLabel}>Sof foyda</div>
            <div className="num" style={{ ...styles.heroValue, color: data.net_profit >= 0 ? "var(--accent)" : "var(--danger)" }}>
              {data.net_profit >= 0 ? "+" : ""}
              {formatMoney(data.net_profit)}
            </div>
            <div style={styles.heroSub}>Foyda marjasi: {formatPercent(data.profit_margin_percent)}</div>
          </div>

          <div style={{ display: "flex", gap: "var(--space-3)" }}>
            <StatCard label="📈 Daromad" value={formatMoney(data.income)} tone="positive" />
            <StatCard label="📉 Xarajat" value={formatMoney(data.expense)} tone="negative" />
          </div>

          <div style={styles.section}>
            <BalanceBeam
              totalAssets={data.total_assets}
              totalLiabilities={data.total_liabilities}
              isBalanced={data.is_balance_sheet_balanced}
            />
          </div>

          <div style={styles.cashRow}>
            <span style={styles.cashLabel}>💵 Kassa qoldig'i</span>
            <span className="num" style={styles.cashValue}>
              {formatMoney(data.cash_closing_balance)}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

function SkeletonHero() {
  return (
    <div style={{ ...styles.hero, opacity: 0.5 }}>
      <div style={styles.heroLabel}>Yuklanmoqda...</div>
      <div style={styles.heroValue}>—</div>
    </div>
  );
}

function ErrorBanner({ text }) {
  return <div style={styles.errorBanner}>❌ {text}</div>;
}

function EmptyState({ text }) {
  return <div style={styles.empty}>{text}</div>;
}

const styles = {
  hero: {
    background: "var(--bg-elevated)",
    border: "1px solid var(--line)",
    borderRadius: "var(--radius-lg)",
    padding: "var(--space-6) var(--space-5)",
    textAlign: "center",
  },
  heroLabel: { fontSize: "var(--text-sm)", color: "var(--ink-muted)", marginBottom: "var(--space-2)" },
  heroValue: { fontSize: "var(--text-hero)", fontWeight: 700, letterSpacing: "-0.02em" },
  heroSub: { fontSize: "var(--text-sm)", color: "var(--ink-muted)", marginTop: "var(--space-2)" },
  section: {
    background: "var(--bg-elevated)",
    border: "1px solid var(--line)",
    borderRadius: "var(--radius-lg)",
  },
  cashRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    background: "var(--bg-elevated)",
    border: "1px solid var(--line)",
    borderRadius: "var(--radius-md)",
    padding: "var(--space-4)",
  },
  cashLabel: { fontSize: "var(--text-sm)", color: "var(--ink-muted)" },
  cashValue: { fontSize: "var(--text-lg)", fontWeight: 600 },
  errorBanner: {
    background: "var(--danger-wash)",
    color: "var(--danger)",
    borderRadius: "var(--radius-md)",
    padding: "var(--space-3) var(--space-4)",
    fontSize: "var(--text-sm)",
  },
  empty: {
    textAlign: "center",
    color: "var(--ink-muted)",
    padding: "var(--space-8) var(--space-4)",
  },
};
