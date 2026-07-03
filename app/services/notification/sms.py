"""
SMS Channel — Eskiz.uz orqali SMS yuborish.

Eskiz O'zbekistondagi eng keng tarqalgan SMS-shlyuzlardan biri (config'da
``ESKIZ_EMAIL`` / ``ESKIZ_PASSWORD`` / ``ESKIZ_FROM`` sifatida allaqachon
ko'zda tutilgan). Avtorizatsiya tokeni vaqtinchalik (~30 kun) amal qiladi,
shu sabab xotirada keshlanadi va muddati o'tganda avtomatik yangilanadi.
"""

from __future__ import annotations

import time

import httpx
from loguru import logger

from app.core.config import settings
from app.models.all_models import User
from app.services.notification.base import (
    NotificationChannelHandler,
    NotificationDeliveryError,
    NotificationPayload,
)

ESKIZ_API_BASE = "https://notify.eskiz.uz/api"
TOKEN_REFRESH_MARGIN_SECONDS = 60 * 60  # tokenni muddatidan 1 soat oldin yangilaymiz


class _TokenCache:
    """Module darajasidagi oddiy token kesh — har yuborishda qayta login qilmaslik uchun."""

    token: str | None = None
    fetched_at: float = 0.0
    ttl_seconds: float = 29 * 24 * 60 * 60  # Eskiz tokeni ~30 kun amal qiladi

    @classmethod
    def is_valid(cls) -> bool:
        return cls.token is not None and (time.time() - cls.fetched_at) < (
            cls.ttl_seconds - TOKEN_REFRESH_MARGIN_SECONDS
        )

    @classmethod
    def set(cls, token: str) -> None:
        cls.token = token
        cls.fetched_at = time.time()


class SMSChannel(NotificationChannelHandler):
    channel_name = "sms"

    def is_configured(self) -> bool:
        return bool(settings.ESKIZ_EMAIL and settings.ESKIZ_PASSWORD)

    def can_reach(self, user: User) -> bool:
        return bool(user.phone)

    async def send(self, user: User, payload: NotificationPayload) -> None:
        if not self.is_configured():
            raise NotificationDeliveryError("ESKIZ_EMAIL/ESKIZ_PASSWORD sozlanmagan")
        if not self.can_reach(user):
            raise NotificationDeliveryError("Foydalanuvchining telefon raqami yo'q")

        token = await self._get_token()
        text = f"{payload.title}: {payload.message}" if payload.title else payload.message
        # Eskiz SMS uzunlik chegarasi ~ 160 belgi (lotin), shuning uchun qisqartiramiz
        text = text[:300]

        phone = user.phone.lstrip("+")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{ESKIZ_API_BASE}/message/sms/send",
                    headers={"Authorization": f"Bearer {token}"},
                    data={
                        "mobile_phone": phone,
                        "message": text,
                        "from": settings.ESKIZ_FROM,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"SMS yuborish xato: user={user.id} | {e}")
            raise NotificationDeliveryError(str(e)) from e

    async def _get_token(self) -> str:
        if _TokenCache.is_valid():
            return _TokenCache.token  # type: ignore[return-value]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{ESKIZ_API_BASE}/auth/login",
                    data={"email": settings.ESKIZ_EMAIL, "password": settings.ESKIZ_PASSWORD},
                )
                response.raise_for_status()
                token = response.json()["data"]["token"]
        except (httpx.HTTPError, KeyError) as e:
            logger.error(f"Eskiz autentifikatsiya xato: {e}")
            raise NotificationDeliveryError(f"Eskiz autentifikatsiya xato: {e}") from e

        _TokenCache.set(token)
        return token
