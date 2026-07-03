import { useEffect, useState } from "react";
import { formatMoney } from "../lib/format";
import "./BalanceBeam.css";

/**
 * Buxgalteriyaning asosiy tenglamasi — Aktivlar = Majburiyatlar + Kapital —
 * shu yerda so'zma-so'z tarozi sifatida chiziladi. Muvozanatda bo'lsa, nur
 * tekis o'rnashadi; buzilgan bo'lsa (bu jiddiy xato belgisi), nur beqaror
 * tebranadi va qizil rangga o'tadi.
 */
export default function BalanceBeam({ totalAssets, totalLiabilities, isBalanced }) {
  const [hasSettled, setHasSettled] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setHasSettled(true), 900);
    return () => clearTimeout(timer);
  }, []);

  const armClass = isBalanced
    ? `balance-beam__arm ${!hasSettled ? "balance-beam__arm--settling" : ""}`
    : "balance-beam__arm balance-beam__arm--unbalanced";

  return (
    <div className="balance-beam">
      <svg className="balance-beam__svg" width="200" height="110" viewBox="0 0 200 110">
        {/* Tayanch (fulcrum) */}
        <polygon points="100,40 88,66 112,66" fill="var(--ink-faint)" />
        <rect x="94" y="66" width="12" height="30" rx="2" fill="var(--ink-faint)" />
        <rect x="70" y="94" width="60" height="6" rx="3" fill="var(--ink-faint)" />

        <g className={armClass}>
          {/* Nur */}
          <rect x="20" y="37" width="160" height="6" rx="3" fill={isBalanced ? "var(--accent)" : "var(--danger)"} />
          {/* Chap taroziga osilgan ip va tovoq — Aktivlar */}
          <line x1="26" y1="40" x2="26" y2="66" stroke="var(--ink-faint)" strokeWidth="1.5" />
          <circle cx="26" cy="74" r="12" fill="none" stroke={isBalanced ? "var(--accent)" : "var(--danger)"} strokeWidth="2.5" />
          {/* O'ng taroziga osilgan ip va tovoq — Majburiyatlar + Kapital */}
          <line x1="174" y1="40" x2="174" y2="66" stroke="var(--ink-faint)" strokeWidth="1.5" />
          <circle cx="174" cy="74" r="12" fill="none" stroke={isBalanced ? "var(--accent)" : "var(--danger)"} strokeWidth="2.5" />
        </g>
      </svg>

      <div className={`balance-beam__status ${isBalanced ? "balance-beam__status--ok" : "balance-beam__status--warn"}`}>
        {isBalanced ? "✅ Muvozanatda" : "⚠️ Muvozanat buzilgan"}
      </div>

      <div className="balance-beam__figures">
        <span>Aktivlar: {formatMoney(totalAssets)}</span>
        <span>Passiv: {formatMoney(totalLiabilities)}</span>
      </div>
    </div>
  );
}
