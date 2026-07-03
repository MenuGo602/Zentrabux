"""
Push Channel — mobil ilova bildirishnomalari.

HOLAT: Hozircha sozlanmagan. Push yuborish uchun provayder (masalan,
Firebase Cloud Messaging) tanlanishi va ``Settings``ga tegishli kalit
(masalan ``FCM_SERVER_KEY``) qo'shilishi, shuningdek foydalanuvchi
qurilma tokenlarini saqlaydigan jadval (``device_tokens``) yaratilishi
kerak — bular hali loyihada yo'q.

``is_configured()`` doimo ``False`` qaytaradi, shu sababli
``NotificationService`` bu kanalni avtomatik chetlab o'tadi va
foydalanuvchi "soxta muvaffaqiyat" haqida noto'g'ri signal olmaydi.
"""

from __future__ import annotations

from app.models.all_models import User
from app.services.notification.base import (
    NotificationChannelHandler,
    NotificationDeliveryError,
    NotificationPayload,
)


class PushChannel(NotificationChannelHandler):
    channel_name = "push"

    def is_configured(self) -> bool:
        return False

    def can_reach(self, user: User) -> bool:
        return False

    async def send(self, user: User, payload: NotificationPayload) -> None:
        raise NotificationDeliveryError(
            "Push kanali hali sozlanmagan — FCM provayder va device_tokens jadvali kerak"
        )
