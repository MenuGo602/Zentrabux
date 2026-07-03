import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { APIError } from "../lib/apiClient";

const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME;

export default function Login() {
  const { loginWithTelegramWidget } = useAuth();
  const navigate = useNavigate();
  const widgetContainerRef = useRef(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    window.onTelegramAuth = async (telegramUser) => {
      setLoading(true);
      setError(null);
      try {
        await loginWithTelegramWidget(telegramUser);
        navigate("/", { replace: true });
      } catch (e) {
        setError(e instanceof APIError ? e.detail : "Kirishda xato yuz berdi");
        setLoading(false);
      }
    };

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", BOT_USERNAME || "");
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "12");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");

    widgetContainerRef.current?.appendChild(script);

    return () => {
      delete window.onTelegramAuth;
    };
  }, [loginWithTelegramWidget, navigate]);

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <svg width="40" height="40" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="7" fill="var(--accent-wash)" />
            <line x1="16" y1="7" x2="16" y2="22" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
            <line x1="7" y1="11" x2="25" y2="11" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
            <circle cx="7" cy="16" r="3.2" fill="none" stroke="var(--accent)" strokeWidth="2" />
            <circle cx="25" cy="16" r="3.2" fill="none" stroke="var(--accent)" strokeWidth="2" />
            <line x1="12" y1="25" x2="20" y2="25" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>

        <h1 style={styles.title}>Zentra</h1>
        <p style={styles.subtitle}>
          Kitoblaringiz muvozanatda. Kirish uchun Telegram hisobingizni tasdiqlang.
        </p>

        {!BOT_USERNAME && (
          <p style={styles.configError}>
            ⚠️ VITE_BOT_USERNAME sozlanmagan. .env fayliga bot username'ini qo'shing.
          </p>
        )}

        <div ref={widgetContainerRef} style={styles.widgetSlot} />

        {loading && <p style={styles.hint}>Kirilmoqda...</p>}
        {error && <p style={styles.error}>❌ {error}</p>}

        <p style={styles.footnote}>
          Hisobingiz yo'qmi? Telegram tugmasini bosish avtomatik ravishda yangi hisob ochadi —
          alohida ro'yxatdan o'tish shart emas.
        </p>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "var(--space-5)",
    background:
      "radial-gradient(circle at 50% 0%, rgba(62,213,152,0.08), transparent 60%), var(--bg)",
  },
  card: {
    width: "100%",
    maxWidth: 380,
    background: "var(--bg-elevated)",
    border: "1px solid var(--line)",
    borderRadius: "var(--radius-lg)",
    padding: "var(--space-8) var(--space-6)",
    textAlign: "center",
  },
  logo: { display: "flex", justifyContent: "center", marginBottom: "var(--space-4)" },
  title: {
    fontSize: "var(--text-2xl)",
    fontWeight: 800,
    margin: 0,
    letterSpacing: "-0.02em",
  },
  subtitle: {
    color: "var(--ink-muted)",
    fontSize: "var(--text-sm)",
    marginTop: "var(--space-2)",
    marginBottom: "var(--space-6)",
    lineHeight: 1.5,
  },
  widgetSlot: { display: "flex", justifyContent: "center", minHeight: 40 },
  hint: { color: "var(--ink-muted)", fontSize: "var(--text-sm)", marginTop: "var(--space-4)" },
  error: { color: "var(--danger)", fontSize: "var(--text-sm)", marginTop: "var(--space-4)" },
  configError: {
    color: "var(--warn)",
    fontSize: "var(--text-xs)",
    background: "var(--warn-wash)",
    padding: "var(--space-2) var(--space-3)",
    borderRadius: "var(--radius-sm)",
    marginBottom: "var(--space-4)",
  },
  footnote: {
    color: "var(--ink-faint)",
    fontSize: "var(--text-xs)",
    marginTop: "var(--space-6)",
    lineHeight: 1.5,
  },
};
