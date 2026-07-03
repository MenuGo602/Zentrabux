"""
AuthMiddleware — har bir xabar/callback kelganda foydalanuvchining
Zentra sessiyasi (JWT) mavjudligini ta'minlaydi.

Agar sessiya yo'q bo'lsa (birinchi murojaat yoki Redis tozalangan bo'lsa),
avtomatik ravishda /auth/telegram orqali kirish/ro'yxatdan o'tish
amalga oshiriladi — foydalanuvchi buni sezmaydi ham.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from loguru import logger

from app.bot.api_client import APIError, api_client
from app.bot.session_store import BotSession, session_store
from app.core.security import decode_token


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            if isinstance(event, Update):
                user = (
                    event.message.from_user if event.message else
                    event.callback_query.from_user if event.callback_query else None
                )
            elif isinstance(event, (Message, CallbackQuery)):
                user = event.from_user

        if user is None:
            return await handler(event, data)

        session = await session_store.get(user.id)
        if session is None:
            detected_lang = user.language_code if user.language_code in ("uz", "ru") else "uz"
            try:
                tokens = await api_client.telegram_login(
                    telegram_id=user.id,
                    full_name=user.full_name or user.username or "Zentra foydalanuvchisi",
                    language=detected_lang,
                )
            except APIError as e:
                logger.error(f"Telegram login xato: telegram_id={user.id} | {e}")
                data["auth_failed"] = True
                return await handler(event, data)

            payload = decode_token(tokens["access_token"])
            session = BotSession(
                telegram_id=user.id,
                user_id=payload.get("sub", ""),
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                language=detected_lang,
            )
            await session_store.set(session)
            data["is_new_user"] = True
        else:
            data["is_new_user"] = False

        data["session"] = session
        data["api"] = api_client
        return await handler(event, data)
