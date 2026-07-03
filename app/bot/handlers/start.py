from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.api_client import APIError, ZentraAPIClient
from app.bot.i18n import t, tset
from app.bot.keyboards import companies_kb, language_kb, main_menu_kb
from app.bot.session_store import BotSession, session_store

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: BotSession, api: ZentraAPIClient, is_new_user: bool):
    name = message.from_user.full_name
    lang = session.language

    try:
        companies = await api.list_companies(session.telegram_id)
    except APIError:
        companies = []

    if is_new_user or not companies:
        await message.answer(t(lang, "welcome.new", name=name), parse_mode="Markdown")
        await message.answer(t(lang, "company.choose"), reply_markup=companies_kb(companies, lang))
        return

    if len(companies) == 1 and not session.active_company_id:
        session.active_company_id = companies[0]["id"]
        session.active_company_name = companies[0]["name"]
        await session_store.set(session)

    await message.answer(t(lang, "welcome.back", name=name), reply_markup=main_menu_kb(lang))


@router.message(Command("help"))
@router.message(F.text.in_(tset("menu.help")))
async def cmd_help(message: Message, session: BotSession):
    await message.answer(t(session.language, "help.text"), parse_mode="Markdown")


@router.message(Command("language"))
@router.message(F.text.in_({"🌐 Til", "🌐 Язык", "/til", "/язык"}))
async def cmd_language(message: Message):
    await message.answer(
        "🌐 Tilni tanlang / Выберите язык:",
        reply_markup=language_kb(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery, session: BotSession):
    new_lang = callback.data.split(":")[-1]
    if new_lang not in ("uz", "ru"):
        await callback.answer()
        return

    session.language = new_lang
    await session_store.set(session)

    confirmation = "✅ Til o'zbekchaga o'zgartirildi" if new_lang == "uz" else "✅ Язык изменён на русский"
    await callback.message.edit_text(confirmation)
    await callback.message.answer(t(new_lang, "welcome.back", name=callback.from_user.full_name), reply_markup=main_menu_kb(new_lang))
    await callback.answer()
