from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.api_client import APIError, ZentraAPIClient
from app.bot.i18n import t, tset
from app.bot.keyboards import cancel_kb, tax_menu_kb
from app.bot.session_store import BotSession
from app.bot.states import VATCalculator
from app.bot.utils import format_money, require_company

router = Router(name="tax")


@router.message(F.text.in_(tset("menu.tax")))
async def show_tax_menu(message: Message, session: BotSession):
    if not await require_company(message, session):
        return
    await message.answer(t(session.language, "tax.choose"), reply_markup=tax_menu_kb(session.language))


@router.callback_query(F.data == "tax:upcoming")
async def show_upcoming_deadlines(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient):
    lang = session.language
    try:
        data = await api.upcoming_tax_deadlines(session.telegram_id, days_ahead=30)
    except APIError as e:
        await callback.answer(t(lang, "common.error", detail=e.detail), show_alert=True)
        return

    await callback.answer()
    deadlines = data["deadlines"]
    if not deadlines:
        await callback.message.answer(t(lang, "tax.no_deadlines"))
        return

    days_word = "kun qoldi" if lang == "uz" else "дн. осталось"
    deadline_word = "Muddat" if lang == "uz" else "Срок"
    header = "📅 Yaqin 30 kundagi soliq muddatlari:" if lang == "uz" else "📅 Налоговые сроки на ближайшие 30 дней:"
    lines = [header, ""]
    for d in deadlines:
        urgency = "🔴" if d["days_remaining"] <= 3 else "🟡" if d["days_remaining"] <= 10 else "🟢"
        lines.append(
            f"{urgency} *{d['tax_name']}* ({d['period']})\n"
            f"   {deadline_word}: {d['deadline']} — {d['days_remaining']} {days_word}"
        )
    await callback.message.answer("\n".join(lines), parse_mode="Markdown")


@router.callback_query(F.data == "tax:vat_calc")
async def start_vat_calc(callback: CallbackQuery, state: FSMContext, session: BotSession):
    lang = session.language
    await state.set_state(VATCalculator.waiting_amount)
    await callback.message.edit_text(t(lang, "tax.ask_amount"))
    await callback.message.answer("↓", reply_markup=cancel_kb(lang))
    await callback.answer()


@router.message(VATCalculator.waiting_amount)
async def finish_vat_calc(
    message: Message, state: FSMContext, session: BotSession, api: ZentraAPIClient
):
    lang = session.language
    raw = message.text.strip().replace(" ", "").replace(",", "")
    if not raw.isdigit():
        await message.answer(t(lang, "tax.invalid_amount"))
        return

    company_id = await require_company(message, session)
    if not company_id:
        await state.clear()
        return

    try:
        result = await api.calculate_vat(session.telegram_id, company_id, amount=float(raw))
    except APIError as e:
        await message.answer(t(lang, "common.error", detail=e.detail))
        await state.clear()
        return

    await state.clear()

    if "message" in result:  # QQS to'lovchisi emas
        await message.answer(f"ℹ️ {result['message']}")
        return

    title = "🧮 *QQS hisob-kitobi*" if lang == "uz" else "🧮 *Расчёт НДС*"
    taxable_word = "Soliqqa tortiladigan summa" if lang == "uz" else "Облагаемая сумма"
    rate_word = "Stavka" if lang == "uz" else "Ставка"
    result_word = "QQS summasi" if lang == "uz" else "Сумма НДС"
    text = (
        f"{title}\n\n"
        f"{taxable_word}: {format_money(float(result['taxable_amount']), lang=lang)}\n"
        f"{rate_word}: {result['rate_percent']}%\n"
        f"*{result_word}: {format_money(float(result['tax_amount']), lang=lang)}*"
    )
    await message.answer(text, parse_mode="Markdown")
