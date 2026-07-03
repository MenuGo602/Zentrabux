from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.api_client import APIError, ZentraAPIClient
from app.bot.i18n import t, tset
from app.bot.keyboards import cancel_kb, counterparty_pick_kb, debt_type_kb, debts_menu_kb
from app.bot.session_store import BotSession
from app.bot.states import DebtCreation
from app.bot.utils import format_money, require_company

router = Router(name="debts")

DEBT_TYPE_LABEL = {
    "receivable": {"uz": "⬅️ Sizga qarzdor", "ru": "⬅️ Должны вам"},
    "payable": {"uz": "➡️ Siz qarzdorsiz", "ru": "➡️ Вы должны"},
}


@router.message(F.text.in_(tset("menu.debts")))
async def show_debts_menu(message: Message, session: BotSession):
    if not await require_company(message, session):
        return
    await message.answer(t(session.language, "debts.choose"), reply_markup=debts_menu_kb(session.language))


@router.callback_query(F.data == "debts:list")
async def list_debts(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient):
    await _render_debt_list(callback, session, api, overdue_only=False)


@router.callback_query(F.data == "debts:overdue")
async def list_overdue_debts(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient):
    await _render_debt_list(callback, session, api, overdue_only=True)


async def _render_debt_list(
    callback: CallbackQuery, session: BotSession, api: ZentraAPIClient, overdue_only: bool
):
    lang = session.language
    company_id = await require_company(callback, session)
    if not company_id:
        return

    try:
        debts = await api.list_debts(session.telegram_id, company_id, overdue_only=overdue_only)
    except APIError as e:
        await callback.answer(t(lang, "common.error", detail=e.detail), show_alert=True)
        return

    await callback.answer()
    if not debts:
        await callback.message.answer(t(lang, "debts.none_overdue" if overdue_only else "debts.none"))
        return

    header = "⏰" if overdue_only else "📋"
    lines = [f"{header} {t(lang, 'debts.overdue_button' if overdue_only else 'debts.list_button')}:", ""]
    for d in debts:
        label = DEBT_TYPE_LABEL.get(d["debt_type"], {}).get(lang, d["debt_type"])
        due_word = "muddat" if lang == "uz" else "срок"
        due = f" · {due_word}: {d['due_date']}" if d.get("due_date") else ""
        remaining_word = "Qoldiq" if lang == "uz" else "Остаток"
        lines.append(f"{label} — {d['description']}\n   {remaining_word}: {format_money(float(d['remaining_amount']), lang=lang)}{due}")
    await callback.message.answer("\n".join(lines))


@router.callback_query(F.data == "debts:aging")
async def show_aging_report(callback: CallbackQuery, session: BotSession, api: ZentraAPIClient):
    lang = session.language
    company_id = await require_company(callback, session)
    if not company_id:
        return

    try:
        aging = await api.debts_aging(session.telegram_id, company_id)
    except APIError as e:
        await callback.answer(t(lang, "common.error", detail=e.detail), show_alert=True)
        return

    await callback.answer()
    title = "📊 Qarzlar tahlili" if lang == "uz" else "📊 Анализ долгов"
    lines = [f"{title} ({aging['as_of']}):", ""]
    bucket_labels = {
        "uz": {
            "current": "Muddati kelmagan", "1-30": "1-30 kun kechikkan", "31-60": "31-60 kun kechikkan",
            "61-90": "61-90 kun kechikkan", "90+": "90+ kun kechikkan",
        },
        "ru": {
            "current": "Срок не наступил", "1-30": "Просрочено 1-30 дн.", "31-60": "Просрочено 31-60 дн.",
            "61-90": "Просрочено 61-90 дн.", "90+": "Просрочено 90+ дн.",
        },
    }[lang]
    you_owed = "sizga" if lang == "uz" else "вам"
    you_owe = "siz" if lang == "uz" else "вы"
    for key, label in bucket_labels.items():
        b = aging["buckets"][key]
        if b["receivable"] == 0 and b["payable"] == 0:
            continue
        lines.append(f"*{label}*: {you_owed} {format_money(b['receivable'], lang=lang)} / {you_owe} {format_money(b['payable'], lang=lang)}")
    await callback.message.answer("\n".join(lines), parse_mode="Markdown")


# ─── Qo'lda qarz qo'shish (FSM) ───────────────────────────────────────────────
@router.callback_query(F.data == "debts:add")
async def start_add_debt(callback: CallbackQuery, session: BotSession):
    if not await require_company(callback, session):
        return
    await callback.message.edit_text(t(session.language, "debt.ask_type"), reply_markup=debt_type_kb(session.language))
    await callback.answer()


@router.callback_query(F.data.startswith("debt_type:"))
async def choose_counterparty(
    callback: CallbackQuery, state: FSMContext, session: BotSession, api: ZentraAPIClient
):
    lang = session.language
    company_id = await require_company(callback, session)
    if not company_id:
        return

    debt_type = callback.data.split(":")[-1]  # receivable | payable
    await state.update_data(debt_type=debt_type)
    await state.set_state(DebtCreation.waiting_counterparty)

    try:
        if debt_type == "receivable":
            items = await api.list_customers(session.telegram_id, company_id)
        else:
            items = await api.list_suppliers(session.telegram_id, company_id)
    except APIError as e:
        await callback.answer(t(lang, "common.error", detail=e.detail), show_alert=True)
        return

    await state.update_data(counterparty_options={i["id"]: i["name"] for i in items})
    prefix = "customer" if debt_type == "receivable" else "supplier"
    await callback.message.edit_text(t(lang, "debt.ask_counterparty"), reply_markup=counterparty_pick_kb(items, prefix, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("customer:pick:") | F.data.startswith("supplier:pick:"))
async def pick_existing_counterparty(callback: CallbackQuery, state: FSMContext, session: BotSession):
    counterparty_id = callback.data.split(":")[-1]
    data = await state.get_data()
    name = data.get("counterparty_options", {}).get(counterparty_id, "?")

    await state.update_data(counterparty_id=counterparty_id, counterparty_name=name)
    await state.set_state(DebtCreation.waiting_description)
    await callback.message.edit_text(t(session.language, "debt.ask_description"))
    await callback.answer()


@router.callback_query(F.data.in_({"customer:new", "supplier:new"}))
async def ask_new_counterparty_name(callback: CallbackQuery, state: FSMContext, session: BotSession):
    kind = "customer" if callback.data == "customer:new" else "supplier"
    await state.update_data(new_counterparty_kind=kind)
    await state.set_state(DebtCreation.waiting_new_counterparty_name)
    await callback.message.edit_text(t(session.language, "debt.ask_new_name"))
    await callback.answer()


@router.message(DebtCreation.waiting_new_counterparty_name)
async def create_new_counterparty(
    message: Message, state: FSMContext, session: BotSession, api: ZentraAPIClient
):
    lang = session.language
    company_id = await require_company(message, session)
    if not company_id:
        await state.clear()
        return

    name = message.text.strip()
    if len(name) < 2:
        await message.answer(t(lang, "company.name_too_short"))
        return

    data = await state.get_data()
    kind = data.get("new_counterparty_kind")

    try:
        if kind == "customer":
            created = await api.create_customer(session.telegram_id, company_id, name=name)
        else:
            created = await api.create_supplier(session.telegram_id, company_id, name=name)
    except APIError as e:
        await message.answer(t(lang, "common.error", detail=e.detail))
        await state.clear()
        return

    await state.update_data(counterparty_id=created["id"], counterparty_name=created["name"])
    await state.set_state(DebtCreation.waiting_description)
    await message.answer(t(lang, "debt.ask_description"))


@router.message(DebtCreation.waiting_description)
async def set_debt_description(message: Message, state: FSMContext, session: BotSession):
    await state.update_data(description=message.text.strip())
    await state.set_state(DebtCreation.waiting_amount)
    await message.answer(t(session.language, "debt.ask_amount"))


@router.message(DebtCreation.waiting_amount)
async def finish_debt_creation(
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

    data = await state.get_data()
    body = {
        "debt_type": data["debt_type"],
        "description": data["description"],
        "original_amount": float(raw),
    }
    if data["debt_type"] == "receivable":
        body["customer_id"] = data["counterparty_id"]
    else:
        body["supplier_id"] = data["counterparty_id"]

    try:
        debt = await api.create_debt(session.telegram_id, company_id, **body)
    except APIError as e:
        await message.answer(t(lang, "common.error", detail=e.detail))
        await state.clear()
        return

    await state.clear()
    await message.answer(t(lang, "debt.created", amount=format_money(float(debt["original_amount"]), lang=lang)))
