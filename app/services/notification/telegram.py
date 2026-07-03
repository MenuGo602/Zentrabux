"""Telegram Channel — Bot API orqali xabar yuborish."""

from __future__ import annotations

import httpx
from loguru import logger

from app.core.config import settings
from app.models.all_models import User
from app.services.notification.base import (
    NotificationChannelHandler,
    NotificationDeliveryError,
    NotificationPayload,
)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramChannel(NotificationChannelHandler):
    channel_name = "telegram"

    def is_configured(self) -> bool:
        return bool(settings.BOT_TOKEN)

    def can_reach(self, user: User) -> bool:
        return user.telegram_id is not None

    async def send(self, user: User, payload: NotificationPayload) -> None:
        if not self.is_configured():
            raise NotificationDeliveryError("BOT_TOKEN sozlanmagan")
        if not self.can_reach(user):
            raise NotificationDeliveryError("Foydalanuvchining telegram_id'si yo'q")

        text = f"*{payload.title}*\n\n{payload.message}" if payload.title else payload.message
        url = f"{TELEGRAM_API_BASE}/bot{settings.BOT_TOKEN}/sendMessage"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": user.telegram_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Telegram yuborish xato: user={user.id} | {e}")
            raise NotificationDeliveryError(str(e)) from e
