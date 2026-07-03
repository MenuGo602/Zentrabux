from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.api_client import APIError, ZentraAPIClient
from app.bot.i18n import t, tset
from app.bot.keyboards import period_kb
from app.bot.session_store import BotSession
from app.bot.utils import format_money, period_bounds, require_company

router = Router(name="dashboard")


@router.message(F.text.in_(tset("menu.dashboard")))
async def show_dashboard_menu(message: Message, session: BotSession):
    if not await require_company(message, session):
        return
    await message.answer(t(session.language, "dashboard.choose_period"), reply_markup=period_kb("dash", session.language))


@router.callback_query(F.data.startswith("dash:"))
async def show_dashboard(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient):
    lang = session.language
    company_id = await require_company(callback, session)
    if not company_id:
        return

    period_key = callback.data.split(":")[-1]
    start, end = period_bounds(period_key)

    try:
        data = await api.dashboard(session.telegram_id, company_id, str(start), str(end))
    except APIError as e:
        await callback.message.edit_text(t(lang, "common.error", detail=e.detail))
        await callback.answer()
        return

    balance_icon = "✅" if data["is_balance_sheet_balanced"] else "⚠️"
    balance_word = t(lang, "dashboard.balanced" if data["is_balance_sheet_balanced"] else "dashboard.not_balanced")

    text = (
        f"📊 *{session.active_company_name}* — {start} — {end}\n\n"
        f"{t(lang, 'dashboard.income')}: {format_money(data['income'], lang=lang)}\n"
        f"{t(lang, 'dashboard.expense')}: {format_money(data['expense'], lang=lang)}\n"
        f"{t(lang, 'dashboard.net_profit')}: {format_money(data['net_profit'], lang=lang)} "
        f"({data['profit_margin_percent']}%)\n\n"
        f"{t(lang, 'dashboard.total_assets')}: {format_money(data['total_assets'], lang=lang)}\n"
        f"{t(lang, 'dashboard.total_liabilities')}: {format_money(data['total_liabilities'], lang=lang)}\n"
        f"{t(lang, 'dashboard.cash_balance')}: {format_money(data['cash_closing_balance'], lang=lang)}\n\n"
        f"{balance_icon} {t(lang, 'dashboard.balance_sheet')} {balance_word}"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=period_kb("dash", lang))
    await callback.answer()
