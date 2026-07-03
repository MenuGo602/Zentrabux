from __future__ import annotations

from datetime import date, timedelta

from aiogram.types import CallbackQuery, Message

from app.bot.i18n import t
from app.bot.session_store import BotSession


async def require_company(target: Message | CallbackQuery, session: BotSession) -> str | None:
    """Faol kompaniya tanlanmagan bo'lsa, ogohlantiradi va None qaytaradi."""
    if session.active_company_id:
        return session.active_company_id

    if isinstance(target, CallbackQuery):
        await target.answer(t(session.language, "common.no_company"), show_alert=True)
    else:
        await target.answer("⚠️ " + t(session.language, "common.no_company"))
    return None


def period_bounds(period_key: str) -> tuple[date, date]:
    """'today' / 'week' / 'month' / 'last_month' kalitidan (boshlanish, tugash) sanalarini hisoblaydi."""
    today = date.today()

    if period_key == "today":
        return today, today
    if period_key == "week":
        return today - timedelta(days=today.weekday()), today
    if period_key == "last_month":
        first_of_this_month = today.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        return last_of_prev_month.replace(day=1), last_of_prev_month
    # default: "month" — shu oy boshidan bugungacha
    return today.replace(day=1), today


def format_money(amount: float, currency: str = "UZS", lang: str = "uz") -> str:
    if currency == "UZS":
        symbol = "so'm" if lang == "uz" else "сум"
    else:
        symbol = currency
    return f"{amount:,.0f} {symbol}".replace(",", " ")
