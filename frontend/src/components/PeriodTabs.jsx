const OPTIONS = [
  { key: "today", label: "Bugun" },
  { key: "week", label: "Hafta" },
  { key: "month", label: "Shu oy" },
  { key: "last_month", label: "O'tgan oy" },
];

export default function PeriodTabs({ value, onChange }) {
  return (
    <div style={styles.wrap} role="tablist" aria-label="Hisobot davri">
      {OPTIONS.map((opt) => {
        const active = opt.key === value;
        return (
          <button
            key={opt.key}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.key)}
            style={{ ...styles.tab, ...(active ? styles.tabActive : {}) }}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

const styles = {
  wrap: {
    display: "flex",
    gap: "var(--space-1)",
    background: "var(--bg-elevated)",
    border: "1px solid var(--line)",
    borderRadius: "var(--radius-md)",
    padding: "4px",
  },
  tab: {
    flex: 1,
    padding: "var(--space-2) var(--space-1)",
    borderRadius: "calc(var(--radius-md) - 4px)",
    fontSize: "var(--text-sm)",
    color: "var(--ink-muted)",
    fontWeight: 500,
    transition: "background 0.15s, color 0.15s",
  },
  tabActive: {
    background: "var(--accent-wash)",
    color: "var(--accent)",
    fontWeight: 700,
  },
};
