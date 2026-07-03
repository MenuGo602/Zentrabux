"""
Celery — Background task queue.

Foydalanuvchini kutdirib qo'ymaydigan ishlar:
- Hisobotlar generatsiyasi
- AI tahlili
- Bildirishnomalar
- Soliq hisob-kitoblari
- AI Memory yangilash
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "zentra",
    broker=settings.CELERY_BROKER_URL or settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND or settings.REDIS_URL,
    include=[
        "app.tasks.reports",
        "app.tasks.notifications",
        "app.tasks.ai_memory",
        "app.tasks.tax_calc",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tashkent",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,          # xatolik bo'lsa qayta bajaradi
    worker_prefetch_multiplier=1,  # har worker 1 ta task
)

# ─── Periodic Tasks ──────────────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Har kuni ertalab 8:00 da muddati o'tgan qarzlarni tekshirish
    "check-overdue-debts": {
        "task": "app.tasks.notifications.check_overdue_debts",
        "schedule": crontab(hour=8, minute=0),
    },
    # Har haftada dushanba 9:00 da haftalik hisobot
    "weekly-report": {
        "task": "app.tasks.reports.generate_weekly_reports",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
    },
    # Har oy 1-sida oylik hisobot
    "monthly-report": {
        "task": "app.tasks.reports.generate_monthly_reports",
        "schedule": crontab(hour=9, minute=0, day_of_month=1),
    },
    # Har kuni kechqurun 18:00 da soliq kalendarini yangilash
    "tax-calendar-check": {
        "task": "app.tasks.tax_calc.check_tax_deadlines",
        "schedule": crontab(hour=18, minute=0),
    },
    # Har kuni tunda 3:00 da eskirgan AI xotiralarni zaiflashtirish
    "ai-memory-decay": {
        "task": "app.tasks.ai_memory.decay_stale_memories",
        "schedule": crontab(hour=3, minute=0),
    },
    # Har kuni tunda 3:15 da muddati o'tgan AI xotiralarni tozalash
    "ai-memory-expire": {
        "task": "app.tasks.ai_memory.expire_memories",
        "schedule": crontab(hour=3, minute=15),
    },
}
