import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, APIError } from "../lib/apiClient";
import { formatMoney } from "../lib/format";

const NEW_COUNTERPARTY = "__new__";

export default function Debts() {
  const { activeCompanyId } = useAuth();
  const [tab, setTab] = useState("all"); // all | overdue | new
  const [debts, setDebts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    if (!activeCompanyId || tab === "new") return;
    setLoading(true);
    api
      .listDebts(activeCompanyId, tab === "overdue")
      .then(setDebts)
      .catch((e) => setError(e instanceof APIError ? e.detail : "Yuklanmadi"))
      .finally(() => setLoading(false));
  }, [activeCompanyId, tab]);

  useEffect(() => {
    load();
  }, [load]);

  if (!activeCompanyId) return <div style={styles.empty}>Avval kompaniya tanlang.</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div style={styles.tabs}>
        <TabButton active={tab === "all"} onClick={() => setTab("all")} label="Barchasi" />
        <TabButton active={tab === "overdue"} onClick={() => setTab("overdue")} label="Muddati o'tgan" />
        <TabButton active={tab === "new"} onClick={() => setTab("new")} label="➕ Yangi" />
      </div>

      {tab === "new" ? (
        <NewDebtForm companyId={activeCompanyId} onCreated={() => setTab("all")} />
      ) : (
        <>
          {loading && <div style={styles.empty}>Yuklanmoqda...</div>}
          {error && <div style={styles.error}>❌ {error}</div>}
          {!loading && !error && debts.length === 0 && (
            <div style={styles.empty}>🎉 Hozircha bu ro'yxat bo'sh.</div>
          )}
          {!loading &&
            debts.map((d) => (
              <div key={d.id} className="ledger-row" style={styles.debtRow}>
                <div style={styles.debtTop}>
                  <span>{d.debt_type === "receivable" ? "⬅️ Sizga qarzdor" : "➡️ Siz qarzdorsiz"}</span>
                  <span className="num" style={{ fontWeight: 700 }}>{formatMoney(d.remaining_amount)}</span>
                </div>
                <div style={styles.debtDesc}>{d.description}</div>
                {d.due_date && <div style={styles.debtMeta}>Muddat: {d.due_date}</div>}
              </div>
            ))}
        </>
      )}
    </div>
  );
}

function TabButton({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        ...styles.tabBtn,
        color: active ? "var(--accent)" : "var(--ink-muted)",
        borderBottomColor: active ? "var(--accent)" : "transparent",
      }}
    >
      {label}
    </button>
  );
}

function NewDebtForm({ companyId, onCreated }) {
  const [debtType, setDebtType] = useState("receivable");
  const [counterparties, setCounterparties] = useState([]);
  const [counterpartyId, setCounterpartyId] = useState("");
  const [newName, setNewName] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loader = debtType === "receivable" ? api.listCustomers : api.listSuppliers;
    loader(companyId).then(setCounterparties).catch(() => setCounterparties([]));
    setCounterpartyId("");
  }, [companyId, debtType]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!description.trim() || !amount || Number(amount) <= 0) {
      setError("Tavsif va summani to'g'ri kiriting");
      return;
    }

    setSubmitting(true);
    try {
      let finalCounterpartyId = counterpartyId;

      if (counterpartyId === NEW_COUNTERPARTY) {
        if (!newName.trim()) {
          setError("Kontragent nomini kiriting");
          setSubmitting(false);
          return;
        }
        const create = debtType === "receivable" ? api.createCustomer : api.createSupplier;
        const created = await create(companyId, { name: newName.trim() });
        finalCounterpartyId = created.id;
      }

      if (!finalCounterpartyId) {
        setError("Kontragentni tanlang yoki yangisini kiriting");
        setSubmitting(false);
        return;
      }

      const body = {
        debt_type: debtType,
        description: description.trim(),
        original_amount: Number(amount),
        ...(debtType === "receivable"
          ? { customer_id: finalCounterpartyId }
          : { supplier_id: finalCounterpartyId }),
      };
      await api.createDebt(companyId, body);
      onCreated();
    } catch (e) {
      setError(e instanceof APIError ? e.detail : "Saqlanmadi");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      <div style={styles.segmentRow}>
        <SegmentButton active={debtType === "receivable"} onClick={() => setDebtType("receivable")} label="⬅️ Sizga qarzdor" />
        <SegmentButton active={debtType === "payable"} onClick={() => setDebtType("payable")} label="➡️ Siz qarzdorsiz" />
      </div>

      <label style={styles.label}>
        Kontragent
        <select
          style={styles.input}
          value={counterpartyId}
          onChange={(e) => setCounterpartyId(e.target.value)}
        >
          <option value="">— Tanlang —</option>
          {counterparties.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
          <option value={NEW_COUNTERPARTY}>➕ Yangi qo'shish</option>
        </select>
      </label>

      {counterpartyId === NEW_COUNTERPARTY && (
        <label style={styles.label}>
          Yangi kontragent nomi
          <input style={styles.input} value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="F.I.Sh yoki tashkilot nomi" />
        </label>
      )}

      <label style={styles.label}>
        Tavsif
        <input style={styles.input} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Masalan: noyabr uchun xizmat" />
      </label>

      <label style={styles.label}>
        Summa (so'mda)
        <input style={styles.input} type="number" min="0" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="500000" />
      </label>

      {error && <div style={styles.error}>❌ {error}</div>}

      <button type="submit" style={styles.submitBtn} disabled={submitting}>
        {submitting ? "Saqlanmoqda..." : "Qarzni saqlash"}
      </button>
    </form>
  );
}

function SegmentButton({ active, onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        ...styles.segmentBtn,
        background: active ? "var(--accent-wash)" : "transparent",
        color: active ? "var(--accent)" : "var(--ink-muted)",
      }}
    >
      {label}
    </button>
  );
}

const styles = {
  tabs: { display: "flex", borderBottom: "1px solid var(--line)" },
  tabBtn: {
    flex: 1,
    padding: "var(--space-3) 0",
    fontSize: "var(--text-sm)",
    fontWeight: 600,
    borderBottom: "2px solid transparent",
  },
  debtRow: {
    background: "var(--bg-elevated)",
    padding: "var(--space-4)",
    borderRadius: "var(--radius-md)",
    marginBottom: "var(--space-2)",
  },
  debtTop: { display: "flex", justifyContent: "space-between", fontSize: "var(--text-sm)" },
  debtDesc: { fontSize: "var(--text-sm)", color: "var(--ink-muted)", marginTop: 4 },
  debtMeta: { fontSize: "var(--text-xs)", color: "var(--ink-faint)", marginTop: 4 },
  empty: { textAlign: "center", color: "var(--ink-muted)", padding: "var(--space-6) var(--space-4)" },
  error: {
    color: "var(--danger)",
    background: "var(--danger-wash)",
    padding: "var(--space-2) var(--space-3)",
    borderRadius: "var(--radius-sm)",
    fontSize: "var(--text-sm)",
  },
  form: { display: "flex", flexDirection: "column", gap: "var(--space-3)" },
  segmentRow: { display: "flex", gap: "var(--space-2)" },
  segmentBtn: {
    flex: 1,
    padding: "var(--space-2)",
    borderRadius: "var(--radius-sm)",
    fontSize: "var(--text-sm)",
    border: "1px solid var(--line)",
  },
  label: { display: "flex", flexDirection: "column", gap: 6, fontSize: "var(--text-xs)", color: "var(--ink-muted)" },
  input: {
    background: "var(--bg-elevated)",
    border: "1px solid var(--line)",
    borderRadius: "var(--radius-sm)",
    padding: "var(--space-3)",
    color: "var(--ink)",
    fontSize: "var(--text-base)",
  },
  submitBtn: {
    background: "var(--accent)",
    color: "#08130e",
    fontWeight: 700,
    padding: "var(--space-3)",
    borderRadius: "var(--radius-sm)",
    marginTop: "var(--space-2)",
  },
};
