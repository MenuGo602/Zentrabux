"""
Zentra Telegram Bot — kirish nuqtasi.

Ishga tushirish:
    python -m app.bot.main

(docker-compose'dagi `bot` xizmati aynan shu buyruqni ishlatadi)
"""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from loguru import logger

from app.bot.handlers import register_all_routers
from app.bot.middlewares import AuthMiddleware
from app.bot.session_store import session_store
from app.core.config import settings


async def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN sozlanmagan. .env faylga BOT_TOKEN=<@BotFather'dan olingan token> qo'shing."
        )

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = RedisStorage.from_url(settings.REDIS_URL)
    dp = Dispatcher(storage=storage)

    auth_middleware = AuthMiddleware()
    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)

    register_all_routers(dp)

    logger.info(f"🤖 Zentra Bot ishga tushmoqda... [{settings.ENVIRONMENT}]")
    logger.info(f"🔗 Backend: {settings.API_BASE_URL}")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await session_store.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot to'xtatildi")
