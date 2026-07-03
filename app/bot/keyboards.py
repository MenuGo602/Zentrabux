"""Bot klaviaturalari — 'lang' parametri orqali uz/ru o'rtasida ishlaydi."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.bot.i18n import t


def main_menu_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    lang_button = "🌐 Til" if lang == "uz" else "🌐 Язык"
    rows = [
        [t(lang, "menu.dashboard"), t(lang, "menu.transactions")],
        [t(lang, "menu.debts"), t(lang, "menu.tax")],
        [t(lang, "menu.companies"), t(lang, "menu.help")],
        [lang_button],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in rows],
        resize_keyboard=True,
    )


def companies_kb(companies: list[dict], lang: str = "uz") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"🏢 {c['name']}", callback_data=f"company:select:{c['id']}")]
        for c in companies
    ]
    rows.append([InlineKeyboardButton(text=t(lang, "company.new_button"), callback_data="company:create")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def period_kb(prefix: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """Hisobot davri tanlash: bugun / shu hafta / shu oy / o'tgan oy."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "period.today"), callback_data=f"{prefix}:today"),
                InlineKeyboardButton(text=t(lang, "period.week"), callback_data=f"{prefix}:week"),
            ],
            [
                InlineKeyboardButton(text=t(lang, "period.month"), callback_data=f"{prefix}:month"),
                InlineKeyboardButton(text=t(lang, "period.last_month"), callback_data=f"{prefix}:last_month"),
            ],
        ]
    )


def transaction_actions_kb(transaction_id: str, status: str, lang: str = "uz") -> InlineKeyboardMarkup:
    rows = []
    if status == "pending":
        confirm_label = "✅ Tasdiqlash" if lang == "uz" else "✅ Подтвердить"
        rows.append([InlineKeyboardButton(text=confirm_label, callback_data=f"tx:confirm:{transaction_id}")])
    invoice_label = "📄 Invoys" if lang == "uz" else "📄 Инвойс"
    act_label = "📄 Akt" if lang == "uz" else "📄 Акт"
    rows.append(
        [
            InlineKeyboardButton(text=invoice_label, callback_data=f"tx:invoice:{transaction_id}"),
            InlineKeyboardButton(text=act_label, callback_data=f"tx:act:{transaction_id}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def debts_menu_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "debts.list_button"), callback_data="debts:list")],
            [InlineKeyboardButton(text=t(lang, "debts.overdue_button"), callback_data="debts:overdue")],
            [InlineKeyboardButton(text=t(lang, "debts.aging_button"), callback_data="debts:aging")],
            [InlineKeyboardButton(text=t(lang, "debts.add_button"), callback_data="debts:add")],
        ]
    )


def debt_type_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    receivable = "⬅️ Menga qarzdor" if lang == "uz" else "⬅️ Должны мне"
    payable = "➡️ Men qarzdorman" if lang == "uz" else "➡️ Я должен"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=receivable, callback_data="debt_type:receivable")],
            [InlineKeyboardButton(text=payable, callback_data="debt_type:payable")],
        ]
    )


def counterparty_pick_kb(items: list[dict], prefix: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """Mavjud mijoz/ta'minotchilar ro'yxati + 'Yangi qo'shish' tugmasi."""
    rows = [
        [InlineKeyboardButton(text=item["name"], callback_data=f"{prefix}:pick:{item['id']}")]
        for item in items[:15]  # Telegram xabar hajmi cheklovi uchun
    ]
    new_label = "➕ Yangisini qo'shish" if lang == "uz" else "➕ Добавить нового"
    rows.append([InlineKeyboardButton(text=new_label, callback_data=f"{prefix}:new")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tax_menu_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "tax.upcoming_button"), callback_data="tax:upcoming")],
            [InlineKeyboardButton(text=t(lang, "tax.vat_calc_button"), callback_data="tax:vat_calc")],
        ]
    )


def language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            ]
        ]
    )


def cancel_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "common.cancel"), callback_data="cancel")]]
    )
