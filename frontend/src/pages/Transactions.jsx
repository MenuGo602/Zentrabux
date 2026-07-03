import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, APIError } from "../lib/apiClient";
import { formatMoney } from "../lib/format";

const TYPE_LABEL = { income: "🟢 Kirim", expense: "🔴 Chiqim", transfer: "🔁 O'tkazma" };
const STATUS_LABEL = { pending: "⏳ Kutilmoqda", confirmed: "✅ Tasdiqlangan", cancelled: "❌ Bekor qilingan" };

export default function Transactions() {
  const { activeCompanyId } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmingId, setConfirmingId] = useState(null);

  const load = useCallback(() => {
    if (!activeCompanyId) return;
    setLoading(true);
    api
      .listTransactions(activeCompanyId, 30)
      .then(setTransactions)
      .catch((e) => setError(e instanceof APIError ? e.detail : "Yuklanmadi"))
      .finally(() => setLoading(false));
  }, [activeCompanyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleConfirm(txId) {
    setConfirmingId(txId);
    try {
      await api.confirmTransaction(activeCompanyId, txId);
      setTransactions((prev) => prev.map((t) => (t.id === txId ? { ...t, status: "confirmed" } : t)));
    } catch (e) {
      setError(e instanceof APIError ? e.detail : "Tasdiqlanmadi");
    } finally {
      setConfirmingId(null);
    }
  }

  if (!activeCompanyId) return <div style={styles.empty}>Avval kompaniya tanlang.</div>;
  if (loading) return <div style={styles.empty}>Yuklanmoqda...</div>;
  if (error) return <div style={styles.error}>❌ {error}</div>;
  if (transactions.length === 0) {
    return (
      <div style={styles.empty}>
        Hali tranzaksiya yo'q. Botga oddiy tilda yozing, masalan:
        <br />
        <em>"500 ming so'mga tovar sotdim"</em>
      </div>
    );
  }

  return (
    <div style={styles.list}>
      {transactions.map((tx) => (
        <div key={tx.id} className="ledger-row" style={styles.row}>
          <div style={styles.rowMain}>
            <div style={styles.rowTop}>
              <span>{TYPE_LABEL[tx.transaction_type] || tx.transaction_type}</span>
              <span className="num" style={{ fontWeight: 700, color: tx.transaction_type === "expense" ? "var(--danger)" : "var(--accent)" }}>
                {tx.transaction_type === "expense" ? "-" : "+"}
                {formatMoney(tx.total_amount, tx.currency)}
              </span>
            </div>
            <div style={styles.rowDesc}>{tx.description}</div>
            <div style={styles.rowMeta}>
              <span>{tx.transaction_date}</span>
              <span>{STATUS_LABEL[tx.status] || tx.status}</span>
            </div>
          </div>
          {tx.status === "pending" && (
            <button
              style={styles.confirmBtn}
              disabled={confirmingId === tx.id}
              onClick={() => handleConfirm(tx.id)}
            >
              {confirmingId === tx.id ? "..." : "✅ Tasdiqlash"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

const styles = {
  list: {
    background: "var(--bg-elevated)",
    border: "1px solid var(--line)",
    borderRadius: "var(--radius-lg)",
    overflow: "hidden",
  },
  row: { padding: "var(--space-4)" },
  rowMain: { display: "flex", flexDirection: "column", gap: 4 },
  rowTop: { display: "flex", justifyContent: "space-between", fontSize: "var(--text-sm)" },
  rowDesc: { fontSize: "var(--text-sm)", color: "var(--ink)" },
  rowMeta: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "var(--text-xs)",
    color: "var(--ink-muted)",
  },
  confirmBtn: {
    marginTop: "var(--space-2)",
    fontSize: "var(--text-xs)",
    color: "var(--accent)",
    fontWeight: 600,
    padding: "var(--space-2)",
    border: "1px solid var(--accent-dim)",
    borderRadius: "var(--radius-sm)",
  },
  empty: { textAlign: "center", color: "var(--ink-muted)", padding: "var(--space-8) var(--space-4)" },
  error: { color: "var(--danger)", padding: "var(--space-4)" },
};
