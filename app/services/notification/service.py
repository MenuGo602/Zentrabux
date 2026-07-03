"""
Notification Service — barcha kanallarni boshqaruvchi yuqori darajadagi servis.

Qoidalar:
    - Har bir bildirishnoma avval ``notifications`` jadvaliga yoziladi
      (audit/tarix uchun), keyin kanallar orqali yuborishga harakat qilinadi.
    - Bitta kanal ishlamasa (sozlanmagan yoki xato), boshqalari baribir
      sinab ko'riladi — foydalanuvchi to'liq bildirishnomasiz qolmaydi.
    - Qaysi kanallar muvaffaqiyatli bo'lgani ``Notification.sent_via``ga yoziladi.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Notification, NotificationChannel, User
from app.services.notification.base import (
    NotificationChannelHandler,
    NotificationDeliveryError,
    NotificationPayload,
)
from app.services.notification.email import EmailChannel
from app.services.notification.push import PushChannel
from app.services.notification.sms import SMSChannel
from app.services.notification.telegram import TelegramChannel

# Ustuvorlik tartibi: avval bepul/tezkor (Telegram), so'ng email, keyin pullik SMS.
DEFAULT_CHANNEL_ORDER: list[NotificationChannelHandler] = [
    TelegramChannel(),
    EmailChannel(),
    SMSChannel(),
    PushChannel(),
]

_CHANNEL_BY_NAME = {c.channel_name: c for c in DEFAULT_CHANNEL_ORDER}


class NotificationService:
    def __init__(self, channels: list[NotificationChannelHandler] | None = None) -> None:
        self._channels = channels or DEFAULT_CHANNEL_ORDER

    async def send(
        self,
        company_id: str,
        user: User,
        notification_type: str,
        title: str,
        message: str,
        db: AsyncSession,
        data: dict | None = None,
        channels: list[NotificationChannel] | None = None,
    ) -> Notification:
        """
        Bildirishnoma yaratadi va belgilangan (yoki barcha mos) kanallar
        orqali yuborishga harakat qiladi.

        ``channels`` berilmasa — foydalanuvchi uchun mavjud va sozlangan
        barcha kanallar ustuvorlik tartibida sinab ko'riladi.
        """
        notification = Notification(
            company_id=company_id,
            user_id=user.id,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data or {},
            sent_via=[],
        )
        db.add(notification)
        await db.flush()

        payload = NotificationPayload(title=title, message=message, data=data)
        candidates = self._resolve_candidates(channels)

        sent_via: list[str] = []
        for channel in candidates:
            if not channel.is_configured() or not channel.can_reach(user):
                continue
            try:
                await channel.send(user, payload)
                sent_via.append(channel.channel_name)
            except NotificationDeliveryError as e:
                logger.warning(f"Bildirishnoma kanali ishlamadi [{channel.channel_name}]: {e}")

        notification.sent_via = sent_via
        await db.flush()

        if not sent_via:
            logger.warning(
                f"Bildirishnoma hech qaysi kanal orqali yetkazilmadi: "
                f"user={user.id} type={notification_type}"
            )

        return notification

    def _resolve_candidates(
        self, channels: list[NotificationChannel] | None
    ) -> list[NotificationChannelHandler]:
        if not channels:
            return self._channels
        return [_CHANNEL_BY_NAME[c] for c in channels if c in _CHANNEL_BY_NAME]
