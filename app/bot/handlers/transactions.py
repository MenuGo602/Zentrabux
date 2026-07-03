from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.bot.api_client import APIError, ZentraAPIClient
from app.bot.i18n import t, tset
from app.bot.keyboards import transaction_actions_kb
from app.bot.session_store import BotSession
from app.bot.utils import format_money, require_company

router = Router(name="transactions")

TX_TYPE_LABEL = {
    "income": {"uz": "🟢 Kirim", "ru": "🟢 Доход"},
    "expense": {"uz": "🔴 Chiqim", "ru": "🔴 Расход"},
    "transfer": {"uz": "🔁 O'tkazma", "ru": "🔁 Перевод"},
}
TX_STATUS_LABEL = {
    "pending": {"uz": "⏳ Kutilmoqda", "ru": "⏳ Ожидает"},
    "confirmed": {"uz": "✅ Tasdiqlangan", "ru": "✅ Подтверждено"},
    "cancelled": {"uz": "❌ Bekor qilingan", "ru": "❌ Отменено"},
}


@router.message(F.text.in_(tset("menu.transactions")))
async def list_recent_transactions(message: Message, session: BotSession, api: ZentraAPIClient):
    lang = session.language
    company_id = await require_company(message, session)
    if not company_id:
        return

    try:
        transactions = await api.list_transactions(session.telegram_id, company_id, limit=10)
    except APIError as e:
        await message.answer(t(lang, "common.error", detail=e.detail))
        return

    if not transactions:
        await message.answer(t(lang, "tx.none_yet"), parse_mode="Markdown")
        return

    await message.answer(t(lang, "tx.recent_header", count=len(transactions)))
    for tx in transactions:
        type_label = TX_TYPE_LABEL.get(tx["transaction_type"], {}).get(lang, tx["transaction_type"])
        status_label = TX_STATUS_LABEL.get(tx["status"], {}).get(lang, tx["status"])
        text = (
            f"{type_label} — {format_money(float(tx['total_amount']), tx['currency'], lang)}\n"
            f"{tx['description']}\n"
            f"📅 {tx['transaction_date']} · {status_label}"
        )
        await message.answer(text, reply_markup=transaction_actions_kb(tx["id"], tx["status"], lang))


@router.callback_query(F.data.startswith("tx:confirm:"))
async def confirm_transaction(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient):
    lang = session.language
    company_id = await require_company(callback, session)
    if not company_id:
        return

    transaction_id = callback.data.split(":")[-1]
    try:
        await api.confirm_transaction(session.telegram_id, company_id, transaction_id)
    except APIError as e:
        await callback.answer(t(lang, "common.error", detail=e.detail), show_alert=True)
        return

    await callback.answer(t(lang, "tx.confirmed"))
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("tx:invoice:"))
async def send_invoice(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient):
    await _send_document(callback, session, api, kind="invoice")


@router.callback_query(F.data.startswith("tx:act:"))
async def send_act(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient):
    await _send_document(callback, session, api, kind="act")


async def _send_document(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient, kind: str):
    lang = session.language
    company_id = await require_company(callback, session)
    if not company_id:
        return

    transaction_id = callback.data.split(":")[-1]
    await callback.answer(t(lang, "tx.doc_preparing"))

    try:
        if kind == "invoice":
            pdf_bytes = await api.generate_invoice(session.telegram_id, company_id, transaction_id)
            filename = f"invoice-{transaction_id[:8]}.pdf"
        else:
            pdf_bytes = await api.generate_act(session.telegram_id, company_id, transaction_id)
            filename = f"akt-{transaction_id[:8]}.pdf"
    except APIError as e:
        await callback.message.answer(t(lang, "tx.doc_failed", detail=e.detail))
        return

    await callback.message.answer_document(BufferedInputFile(pdf_bytes, filename=filename))
