"""
Bot i18n — o'zbek va rus tillari.

Dizayn: oddiy dict-asoslangan lug'at (to'liq i18n freymvork emas — bot
uchun bu yetarli va ortiqcha murakkablikni oldini oladi). Til
`BotSession.language` orqali saqlanadi ('uz' yoki 'ru'), backend
`User.language` ustuniga /auth/telegram orqali yoziladi.
"""

from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    # ─── Asosiy menyu tugmalari ───────────────────────────────────────────
    "menu.dashboard": {"uz": "📊 Dashboard", "ru": "📊 Дашборд"},
    "menu.transactions": {"uz": "🧾 Tranzaksiyalar", "ru": "🧾 Транзакции"},
    "menu.debts": {"uz": "💳 Qarzlar", "ru": "💳 Долги"},
    "menu.tax": {"uz": "📅 Soliq", "ru": "📅 Налоги"},
    "menu.companies": {"uz": "🏢 Kompaniyalar", "ru": "🏢 Компании"},
    "menu.help": {"uz": "❓ Yordam", "ru": "❓ Помощь"},

    # ─── Xush kelibsiz / yordam ───────────────────────────────────────────
    "welcome.new": {
        "uz": (
            "👋 Assalomu alaykum, {name}!\n\n"
            "Men *Zentra* — sun'iy intellekt asosidagi buxgalteriya yordamchingizman.\n\n"
            "Men bilan oddiy tilda gaplashishingiz mumkin, masalan:\n"
            "• _\"500 ming so'mga tovar sotdim\"_\n"
            "• _\"Aziz 200 ming qarzini to'ladi\"_\n"
            "• _\"kassada qancha pul bor?\"_\n\n"
            "Avval kompaniyangizni sozlaymiz 👇"
        ),
        "ru": (
            "👋 Здравствуйте, {name}!\n\n"
            "Я *Zentra* — ваш бухгалтерский помощник на основе ИИ.\n\n"
            "Со мной можно общаться обычным языком, например:\n"
            "• _\"продал товар на 500 тысяч сум\"_\n"
            "• _\"Азиз погасил долг 200 тысяч\"_\n"
            "• _\"сколько денег в кассе?\"_\n\n"
            "Сначала настроим вашу компанию 👇"
        ),
    },
    "welcome.back": {
        "uz": "👋 Xush kelibsiz, {name}! Nima bilan yordam bera olaman?",
        "ru": "👋 С возвращением, {name}! Чем могу помочь?",
    },
    "help.text": {
        "uz": (
            "*Zentra Bot — qo'llanma*\n\n"
            "📊 *Dashboard* — joriy davr uchun daromad/xarajat/foyda\n"
            "🧾 *Tranzaksiyalar* — so'nggi yozuvlar, tasdiqlash, hujjat olish\n"
            "💳 *Qarzlar* — kimga qarzdorsiz, kim sizga qarzdor\n"
            "📅 *Soliq* — yaqin muddatlar, QQS kalkulyatori\n"
            "🏢 *Kompaniyalar* — kompaniya almashtirish/qo'shish\n\n"
            "✍️ Oddiy xabar yozsangiz — AI uni tushunib, tranzaksiya yaratadi\n"
            "📷 Chek/faktura rasmini yuborsangiz — AI undan ma'lumot o'qiydi"
        ),
        "ru": (
            "*Zentra Bot — справка*\n\n"
            "📊 *Дашборд* — доход/расход/прибыль за период\n"
            "🧾 *Транзакции* — последние записи, подтверждение, документы\n"
            "💳 *Долги* — кому должны вы, кто должен вам\n"
            "📅 *Налоги* — ближайшие сроки, калькулятор НДС\n"
            "🏢 *Компании* — переключение/добавление компании\n\n"
            "✍️ Напишите обычным текстом — ИИ поймёт и создаст транзакцию\n"
            "📷 Отправьте фото чека — ИИ прочитает данные с него"
        ),
    },

    # ─── Umumiy ───────────────────────────────────────────────────────────
    "common.cancel": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена"},
    "common.cancelled": {"uz": "Bekor qilindi.", "ru": "Отменено."},
    "common.no_company": {
        "uz": "Avval faol kompaniyani tanlang: 🏢 Kompaniyalar tugmasini bosing.",
        "ru": "Сначала выберите активную компанию: нажмите 🏢 Компании.",
    },
    "common.error": {"uz": "❌ Xato: {detail}", "ru": "❌ Ошибка: {detail}"},

    # ─── Kompaniya ──────────────────────────────────────────────────────
    "company.choose": {"uz": "Kompaniyani tanlang:", "ru": "Выберите компанию:"},
    "company.none_yet": {
        "uz": "Sizda hali kompaniya yo'q. Keling, birinchisini yarataylik 👇",
        "ru": "У вас пока нет компании. Давайте создадим первую 👇",
    },
    "company.new_button": {"uz": "➕ Yangi kompaniya", "ru": "➕ Новая компания"},
    "company.ask_name": {
        "uz": "Kompaniyangiz nomini yozing (masalan: \"Zentra Tech MChJ\"):",
        "ru": "Введите название компании (например: \"Zentra Tech ООО\"):",
    },
    "company.name_too_short": {
        "uz": "Nom juda qisqa. Qaytadan urinib ko'ring:",
        "ru": "Название слишком короткое. Попробуйте ещё раз:",
    },
    "company.created": {
        "uz": (
            "✅ *{name}* yaratildi va faol kompaniya sifatida tanlandi!\n\n"
            "Endi menga oddiy tilda tranzaksiya yozib ko'ring, masalan:\n"
            "_\"500 ming so'mga xizmat ko'rsatdim\"_"
        ),
        "ru": (
            "✅ *{name}* создана и выбрана как активная компания!\n\n"
            "Теперь напишите транзакцию обычным текстом, например:\n"
            "_\"оказал услугу на 500 тысяч сум\"_"
        ),
    },
    "company.selected": {"uz": "✅ Faol kompaniya: *{name}*", "ru": "✅ Активная компания: *{name}*"},
    "company.main_menu": {"uz": "Asosiy menyu:", "ru": "Главное меню:"},

    # ─── Dashboard ──────────────────────────────────────────────────────
    "dashboard.choose_period": {"uz": "Qaysi davr uchun?", "ru": "За какой период?"},
    "period.today": {"uz": "Bugun", "ru": "Сегодня"},
    "period.week": {"uz": "Shu hafta", "ru": "Эта неделя"},
    "period.month": {"uz": "Shu oy", "ru": "Этот месяц"},
    "period.last_month": {"uz": "O'tgan oy", "ru": "Прошлый месяц"},

    # ─── Qarzlar ────────────────────────────────────────────────────────
    "debts.choose": {"uz": "Nimani ko'rmoqchisiz?", "ru": "Что хотите посмотреть?"},
    "debts.list_button": {"uz": "📋 Barcha qarzlar", "ru": "📋 Все долги"},
    "debts.overdue_button": {"uz": "⏰ Muddati o'tganlar", "ru": "⏰ Просроченные"},
    "debts.aging_button": {"uz": "📊 Muddat bo'yicha tahlil", "ru": "📊 Анализ по срокам"},
    "debts.add_button": {"uz": "➕ Yangi qarz qo'shish", "ru": "➕ Добавить долг"},
    "debts.none": {"uz": "🎉 Hozircha qarz yo'q.", "ru": "🎉 Долгов пока нет."},
    "debts.none_overdue": {"uz": "🎉 Hozircha muddati o'tgan qarz yo'q.", "ru": "🎉 Просроченных долгов нет."},

    # ─── Soliq ──────────────────────────────────────────────────────────
    "tax.choose": {"uz": "Nimani bilmoqchisiz?", "ru": "Что вас интересует?"},
    "tax.upcoming_button": {"uz": "📅 Yaqin muddatlar", "ru": "📅 Ближайшие сроки"},
    "tax.vat_calc_button": {"uz": "🧮 QQS kalkulyatori", "ru": "🧮 Калькулятор НДС"},
    "tax.no_deadlines": {
        "uz": "Keyingi 30 kun ichida soliq muddati yo'q. 👍",
        "ru": "В ближайшие 30 дней налоговых сроков нет. 👍",
    },
    "tax.ask_amount": {
        "uz": "Summani kiriting (so'mda), masalan: 5000000",
        "ru": "Введите сумму (в сумах), например: 5000000",
    },
    "tax.invalid_amount": {
        "uz": "Iltimos, faqat raqam kiriting (masalan: 5000000):",
        "ru": "Пожалуйста, введите только число (например: 5000000):",
    },

    # ─── Dashboard maydonlari ───────────────────────────────────────────
    "dashboard.income": {"uz": "📈 Daromad", "ru": "📈 Доход"},
    "dashboard.expense": {"uz": "📉 Xarajat", "ru": "📉 Расход"},
    "dashboard.net_profit": {"uz": "💰 Sof foyda", "ru": "💰 Чистая прибыль"},
    "dashboard.total_assets": {"uz": "🏦 Jami aktivlar", "ru": "🏦 Всего активов"},
    "dashboard.total_liabilities": {"uz": "📋 Jami majburiyatlar", "ru": "📋 Всего обязательств"},
    "dashboard.cash_balance": {"uz": "💵 Kassa qoldig'i", "ru": "💵 Остаток кассы"},
    "dashboard.balanced": {"uz": "muvozanatda", "ru": "сбалансирован"},
    "dashboard.not_balanced": {"uz": "muvozanatda emas", "ru": "не сбалансирован"},
    "dashboard.balance_sheet": {"uz": "Balans", "ru": "Баланс"},

    # ─── Tranzaksiyalar ─────────────────────────────────────────────────
    "tx.none_yet": {
        "uz": "Hali tranzaksiya yo'q. Menga oddiy tilda yozing, masalan:\n_\"300 ming so'mga tovar sotdim\"_",
        "ru": "Транзакций пока нет. Напишите обычным текстом, например:\n_\"продал товар на 300 тысяч сум\"_",
    },
    "tx.recent_header": {"uz": "So'nggi {count} ta tranzaksiya:", "ru": "Последние {count} транзакций:"},
    "tx.confirmed": {"uz": "✅ Tasdiqlandi", "ru": "✅ Подтверждено"},
    "tx.doc_preparing": {"uz": "Tayyorlanmoqda...", "ru": "Подготавливается..."},
    "tx.doc_failed": {"uz": "❌ Hujjat yaratilmadi: {detail}", "ru": "❌ Документ не создан: {detail}"},

    # ─── Qarz qo'shish (FSM) ────────────────────────────────────────────
    "debt.ask_type": {"uz": "Qarz turini tanlang:", "ru": "Выберите тип долга:"},
    "debt.ask_counterparty": {
        "uz": "Kim bilan bog'liq? Ro'yxatdan tanlang yoki yangisini qo'shing:",
        "ru": "С кем связан долг? Выберите из списка или добавьте нового:",
    },
    "debt.ask_new_name": {
        "uz": "Ism/nomini kiriting:",
        "ru": "Введите имя/название:",
    },
    "debt.ask_description": {"uz": "Qarz haqida qisqacha yozing (masalan: \"tovar uchun\"):", "ru": "Кратко опишите долг (например: \"за товар\"):"},
    "debt.ask_amount": {"uz": "Summani kiriting (so'mda):", "ru": "Введите сумму (в сумах):"},
    "debt.created": {"uz": "✅ Qarz qo'shildi: {amount}", "ru": "✅ Долг добавлен: {amount}"},

    # ─── AI chat / OCR ──────────────────────────────────────────────────
    "ai.error": {"uz": "❌ AI xatosi: {detail}", "ru": "❌ Ошибка ИИ: {detail}"},
    "ocr.read_failed": {"uz": "❌ Rasmni o'qib bo'lmadi: {detail}", "ru": "❌ Не удалось прочитать фото: {detail}"},
    "ocr.amount_not_found": {
        "uz": "🤔 Rasmdan summani aniqlay olmadim. Iltimos, summani yozib yuboring, masalan: \"120 000 so'mga xarajat\".",
        "ru": "🤔 Не смог определить сумму на фото. Напишите сумму текстом, например: \"расход 120 000 сум\".",
    },
    "ocr.header": {"uz": "🧾 Chekdan o'qilgan ma'lumot:", "ru": "🧾 Данные, считанные с чека:"},
    "ocr.confirm_question": {"uz": "Xarajat sifatida qo'shaymi?", "ru": "Добавить как расход?"},
    "ocr.confirm_button": {"uz": "✅ Xarajat sifatida qo'shish", "ru": "✅ Добавить как расход"},
    "ocr.stale": {"uz": "Ma'lumot eskirgan, qaytadan rasm yuboring", "ru": "Данные устарели, отправьте фото заново"},
    "ocr.tx_failed": {"uz": "❌ Tranzaksiya yaratilmadi: {detail}", "ru": "❌ Транзакция не создана: {detail}"},
    "ocr.tx_created": {"uz": "✅ Xarajat qo'shildi: {amount}", "ru": "✅ Расход добавлен: {amount}"},
    "ocr.default_description": {"uz": "Chekdan qo'shildi", "ru": "Добавлено с чека"},
}


def t(lang: str, key: str, **kwargs) -> str:
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry.get("uz", key)
    return text.format(**kwargs) if kwargs else text


def tset(*keys: str) -> set[str]:
    """Bir nechta kalitning HAR IKKALA tildagi matnini to'plam sifatida qaytaradi.

    Reply-klaviatura tugmalarini F.text filter bilan ushlashda ishlatiladi —
    foydalanuvchi tili o'zgargan taqdirda ham eski til tugmasi hali
    ekranda qolgan bo'lsa ham ishlab turishi uchun HAR IKKI tildagi
    variantlar filterga qo'shiladi.
    """
    result = set()
    for key in keys:
        entry = TRANSLATIONS.get(key, {})
        result.update(entry.values())
    return result
