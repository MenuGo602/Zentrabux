"""
Notification Service — kanal interfeysi.

Har bir kanal (Telegram, Email, SMS, Push) shu interfeysni amalga
oshiradi va o'zining yetkazib berish mantiqiga javobgar bo'ladi.
Yuqori darajadagi ``NotificationService`` qaysi kanal ishlamasa ham
qolganlarini davom ettiradi — bitta kanalning ishdan chiqishi
foydalanuvchini bildirishnomasiz qoldirmasligi kerak.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.all_models import User


@dataclass
class NotificationPayload:
    title: str
    message: str
    data: dict | None = None


class NotificationDeliveryError(Exception):
    """Kanal orqali yetkazib berish muvaffaqiyatsiz tugaganda ko'tariladi."""


class NotificationChannelHandler(ABC):
    """Barcha bildirishnoma kanallari shu interfeysni amalga oshiradi."""

    channel_name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """Bu kanal uchun kerakli sozlamalar (.env) to'ldirilganmi."""
        ...

    @abstractmethod
    def can_reach(self, user: User) -> bool:
        """Foydalanuvchida shu kanal orqali yetkazib berish uchun yetarli ma'lumot bormi."""
        ...

    @abstractmethod
    async def send(self, user: User, payload: NotificationPayload) -> None:
        """
        Bildirishnoma yuboradi.

        Muvaffaqiyatsiz bo'lsa ``NotificationDeliveryError`` ko'taradi —
        chaqiruvchi (``NotificationService``) buni yutib, boshqa kanallarni
        davom ettiradi.
        """
        ...
