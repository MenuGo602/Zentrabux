export default function StatCard({ label, value, tone = "neutral", sub }) {
  const toneColor =
    tone === "positive" ? "var(--accent)" : tone === "negative" ? "var(--danger)" : "var(--ink)";

  return (
    <div style={styles.card}>
      <div style={styles.label}>{label}</div>
      <div className="num" style={{ ...styles.value, color: toneColor }}>
        {value}
      </div>
      {sub && <div style={styles.sub}>{sub}</div>}
    </div>
  );
}

const styles = {
  card: {
    background: "var(--bg-elevated)",
    border: "1px solid var(--line)",
    borderRadius: "var(--radius-md)",
    padding: "var(--space-4)",
    flex: 1,
    minWidth: 0,
  },
  label: {
    fontSize: "var(--text-xs)",
    color: "var(--ink-muted)",
    marginBottom: "var(--space-2)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  value: {
    fontSize: "var(--text-lg)",
    fontWeight: 600,
  },
  sub: {
    fontSize: "var(--text-xs)",
    color: "var(--ink-faint)",
    marginTop: "var(--space-1)",
  },
};
