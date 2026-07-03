export function formatMoney(amount, currency = "UZS") {
  const n = Math.round(Number(amount) || 0);
  const formatted = n.toLocaleString("uz-UZ").replace(/,/g, " ");
  const symbol = currency === "UZS" ? "so'm" : currency;
  return `${formatted} ${symbol}`;
}

export function formatPercent(value) {
  const n = Number(value) || 0;
  return `${n.toFixed(1)}%`;
}

/** 'today' | 'week' | 'month' | 'last_month' -> {start, end} (YYYY-MM-DD) */
export function periodBounds(key) {
  const today = new Date();
  const toISO = (d) => d.toISOString().slice(0, 10);

  if (key === "today") return { start: toISO(today), end: toISO(today) };

  if (key === "week") {
    const day = today.getDay() === 0 ? 7 : today.getDay(); // Yakshanba=7 (dushanbadan boshlanadi)
    const monday = new Date(today);
    monday.setDate(today.getDate() - (day - 1));
    return { start: toISO(monday), end: toISO(today) };
  }

  if (key === "last_month") {
    const firstOfThisMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastOfPrevMonth = new Date(firstOfThisMonth - 86400000);
    const firstOfPrevMonth = new Date(lastOfPrevMonth.getFullYear(), lastOfPrevMonth.getMonth(), 1);
    return { start: toISO(firstOfPrevMonth), end: toISO(lastOfPrevMonth) };
  }

  // default: "month"
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  return { start: toISO(firstOfMonth), end: toISO(today) };
}
