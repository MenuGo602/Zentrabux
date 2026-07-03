"""
AI suhbat va OCR handlerlari.

Bu — botning "yuragi": foydalanuvchi menyu tugmalarisiz, oddiy tilda
yozadi ("500 mingga tovar sotdim"), bot esa buni backend'dagi AI
Orchestrator'ga uzatadi. Bot o'zi HECH QANDAY niyatni aniqlamaydi —
faqat xabarni backend'ga yuboradi va tabiiy tildagi javobni ko'rsatadi.

Bu router eng OXIRIDA ro'yxatdan o'tkaziladi (handlers/__init__.py'da),
shunda menyu tugmalari va FSM holatlari birinchi navbatda o'z
handlerlariga tushadi, qolgan har qanday erkin matn shu yerga — AI
chatga tushadi.
"""

from __future__ import annotations

import base64
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.api_client import APIError, ZentraAPIClient
from app.bot.i18n import t
from app.bot.session_store import BotSession, session_store
from app.bot.utils import format_money, require_company

router = Router(name="ai_chat")


def _ocr_confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=t(lang, "ocr.confirm_button"), callback_data="ocr:confirm"),
            InlineKeyboardButton(text=t(lang, "common.cancel"), callback_data="cancel"),
        ]]
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(
    message: Message, session: BotSession, api: ZentraAPIClient, state: FSMContext
):
    """Menyu tugmalari va FSM holatlari ushlamagan har qanday matn — AI chatga boradi."""
    lang = session.language
    company_id = await require_company(message, session)
    if not company_id:
        return

    ai_session_id = await session_store.get_ai_session_id(session.telegram_id, company_id)

    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        response = await api.ai_chat(session.telegram_id, company_id, message.text, ai_session_id)
    except APIError as e:
        await message.answer(t(lang, "ai.error", detail=e.detail))
        return

    if response.get("session_id"):
        await session_store.set_ai_session_id(session.telegram_id, company_id, response["session_id"])

    await message.answer(response["message"])

    tx = response.get("transaction")
    if tx:
        await message.answer(
            f"📝 {tx.get('description', '')}\n"
            f"💰 {format_money(float(tx['total_amount']), tx.get('currency', 'UZS'), lang)}"
        )


@router.message(F.photo)
async def handle_receipt_photo(
    message: Message, session: BotSession, api: ZentraAPIClient, state: FSMContext
):
    """Chek/faktura rasmi — OCR orqali ma'lumot o'qiladi, so'ng tasdiqlash so'raladi."""
    lang = session.language
    company_id = await require_company(message, session)
    if not company_id:
        return

    await message.bot.send_chat_action(message.chat.id, "upload_photo")

    photo = message.photo[-1]  # eng katta o'lchamdagi versiya
    file = await message.bot.get_file(photo.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    image_base64 = base64.b64encode(file_bytes.read()).decode()

    try:
        result = await api.ai_ocr(session.telegram_id, company_id, image_base64, "image/jpeg")
    except APIError as e:
        await message.answer(t(lang, "ocr.read_failed", detail=e.detail))
        return

    if not result.get("total_amount"):
        await message.answer(t(lang, "ocr.amount_not_found"))
        return

    await state.update_data(ocr_result=result)

    lines = [t(lang, "ocr.header"), ""]
    if result.get("merchant_name"):
        lines.append(f"🏪 {result['merchant_name']}")
    lines.append(f"💰 {format_money(float(result['total_amount']), result.get('currency', 'UZS'), lang)}")
    if result.get("purchase_date"):
        lines.append(f"📅 {result['purchase_date']}")
    lines.append("")
    lines.append(t(lang, "ocr.confirm_question"))

    await message.answer("\n".join(lines), reply_markup=_ocr_confirm_kb(lang))


@router.callback_query(F.data == "ocr:confirm")
async def confirm_ocr_transaction(
    callback: CallbackQuery, state: FSMContext, session: BotSession, api: ZentraAPIClient
):
    lang = session.language
    company_id = await require_company(callback, session)
    if not company_id:
        return

    data = await state.get_data()
    ocr_result = data.get("ocr_result")
    if not ocr_result:
        await callback.answer(t(lang, "ocr.stale"), show_alert=True)
        return

    try:
        tx_result = await api.create_transaction(
            session.telegram_id,
            company_id,
            transaction_date=ocr_result.get("purchase_date") or str(date.today()),
            description=ocr_result.get("merchant_name") or t(lang, "ocr.default_description"),
            transaction_type="expense",
            total_amount=ocr_result["total_amount"],
            currency=ocr_result.get("currency", "UZS"),
            ai_generated=True,
            ai_confidence=ocr_result.get("confidence", 0),
        )
    except APIError as e:
        await callback.message.edit_text(t(lang, "ocr.tx_failed", detail=e.detail))
        await callback.answer()
        return

    await state.update_data(ocr_result=None)
    await callback.message.edit_text(t(lang, "ocr.tx_created", amount=format_money(float(tx_result["total_amount"]), lang=lang)))
    await callback.answer()
