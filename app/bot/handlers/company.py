from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.api_client import APIError, ZentraAPIClient
from app.bot.i18n import t, tset
from app.bot.keyboards import cancel_kb, companies_kb, main_menu_kb
from app.bot.session_store import BotSession, session_store
from app.bot.states import CompanyOnboarding

router = Router(name="company")


@router.message(F.text.in_(tset("menu.companies")))
async def show_companies(message: Message, session: BotSession, api: ZentraAPIClient):
    lang = session.language
    try:
        companies = await api.list_companies(session.telegram_id)
    except APIError as e:
        await message.answer(t(lang, "common.error", detail=e.detail))
        return

    if not companies:
        await message.answer(t(lang, "company.none_yet"))
    await message.answer(t(lang, "company.choose"), reply_markup=companies_kb(companies, lang))


@router.callback_query(F.data.startswith("company:select:"))
async def select_company(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient):
    lang = session.language
    company_id = callback.data.split(":")[-1]

    try:
        companies = await api.list_companies(session.telegram_id)
    except APIError as e:
        await callback.answer(t(lang, "common.error", detail=e.detail), show_alert=True)
        return

    company = next((c for c in companies if c["id"] == company_id), None)
    if not company:
        await callback.answer("Not found" if lang != "uz" else "Topilmadi", show_alert=True)
        return

    session.active_company_id = company["id"]
    session.active_company_name = company["name"]
    await session_store.set(session)

    await callback.message.edit_text(t(lang, "company.selected", name=company["name"]), parse_mode="Markdown")
    await callback.message.answer(t(lang, "company.main_menu"), reply_markup=main_menu_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "company:create")
async def start_create_company(callback: CallbackQuery, state: FSMContext, session: BotSession):
    lang = session.language
    await state.set_state(CompanyOnboarding.waiting_name)
    await callback.message.edit_text(t(lang, "company.ask_name"))
    await callback.message.answer("↓", reply_markup=cancel_kb(lang))
    await callback.answer()


@router.message(CompanyOnboarding.waiting_name)
async def finish_create_company(
    message: Message, state: FSMContext, session: BotSession, api: ZentraAPIClient
):
    lang = session.language
    name = message.text.strip()
    if len(name) < 2:
        await message.answer(t(lang, "company.name_too_short"))
        return

    try:
        company = await api.create_company(session.telegram_id, name=name)
    except APIError as e:
        await message.answer(t(lang, "common.error", detail=e.detail))
        return

    await state.clear()

    session.active_company_id = company["id"]
    session.active_company_name = company["name"]
    await session_store.set(session)

    await message.answer(
        t(lang, "company.created", name=company["name"]),
        parse_mode="Markdown",
        reply_markup=main_menu_kb(lang),
    )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext, session: BotSession):
    await state.clear()
    await callback.message.edit_text(t(session.language, "common.cancelled"))
    await callback.answer()
