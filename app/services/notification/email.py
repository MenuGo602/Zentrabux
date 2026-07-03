"""Email Channel — SMTP orqali xabar yuborish (aiosmtplib)."""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib
from loguru import logger

from app.core.config import settings
from app.models.all_models import User
from app.services.notification.base import (
    NotificationChannelHandler,
    NotificationDeliveryError,
    NotificationPayload,
)


class EmailChannel(NotificationChannelHandler):
    channel_name = "email"

    def is_configured(self) -> bool:
        return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)

    def can_reach(self, user: User) -> bool:
        return bool(user.email)

    async def send(self, user: User, payload: NotificationPayload) -> None:
        if not self.is_configured():
            raise NotificationDeliveryError("SMTP sozlamalari to'liq emas")
        if not self.can_reach(user):
            raise NotificationDeliveryError("Foydalanuvchining email manzili yo'q")

        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = user.email
        message["Subject"] = payload.title or "Zentra bildirishnomasi"
        message.set_content(payload.message)

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                start_tls=True,
            )
        except (aiosmtplib.SMTPException, OSError) as e:
            logger.error(f"Email yuborish xato: user={user.id} | {e}")
            raise NotificationDeliveryError(str(e)) from e
