from aiogram import Dispatcher

from app.bot.handlers import ai_chat, company, dashboard, debts, start, tax, transactions


def register_all_routers(dp: Dispatcher) -> None:
    """
    Tartib MUHIM: aiogram xabarni birinchi mos keladigan routerga yuboradi.

    Aniq menyu tugmalari va FSM holatlari ('company', 'dashboard', ...)
    birinchi bo'lib tekshirilishi kerak. 'ai_chat' esa eng oxirida —
    u har qanday oddiy matnni ("catch-all") AI suhbat sifatida qabul qiladi.
    """
    dp.include_router(start.router)
    dp.include_router(company.router)
    dp.include_router(dashboard.router)
    dp.include_router(transactions.router)
    dp.include_router(debts.router)
    dp.include_router(tax.router)
    dp.include_router(ai_chat.router)  # eng oxirida — catch-all
