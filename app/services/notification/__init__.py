"""
Notification Service — ko'p kanalli bildirishnoma yuborish tizimi.

Qo'llab-quvvatlanadigan kanallar:
    - Telegram (Bot API)
    - Email (SMTP)
    - SMS (Eskiz.uz)
    - Push (hozircha sozlanmagan — provayder tanlanishi kutilmoqda)

Yuqori darajadagi kirish nuqtasi — ``NotificationService``.
"""

from app.services.notification.service import NotificationService

__all__ = ["NotificationService"]
