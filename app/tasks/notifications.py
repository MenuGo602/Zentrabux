"""
Bildirishnoma background task'lari.

Har kuni ertalab muddati o'tgan qarzlarni tekshiradi va tegishli
foydalanuvchilarga eslatma yuboradi. Bitta xabarnoma yozish/yuborish
xatosi butun task'ni to'xtatib qo'ymasligi uchun har bir qarz/kompaniya
alohida try/except bilan qayta ishlanadi.
"""

from __future__ import annotations

from datetime import date

from loguru import logger

from app.tasks.celery_app import celery_app


@celery_app.task(name="notifications.check_overdue_debts")
def check_overdue_debts() -> dict:
    """Muddati o'tgan barcha qarzlarni topadi va egalariga eslatma yuboradi."""
    import asyncio

    return asyncio.run(_check_overdue_debts_async())


@celery_app.task(name="notifications.send_notification")
def send_notification_task(
    company_id: str,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> dict:
    """Bitta bildirishnomani orqa fonda yuborish (masalan, AI orchestrator'dan chaqirilganda)."""
    import asyncio

    return asyncio.run(
        _send_single_notification(company_id, user_id, notification_type, title, message, data)
    )


async def _check_overdue_debts_async() -> dict:
    from sqlalchemy import select

    from app.core.database import AsyncSessionFactory
    from app.models.all_models import CompanyUser, Debt, DebtStatus, DebtType, User
    from app.services.notification.service import NotificationService

    notification_service = NotificationService()
    notified = 0
    failed = 0

    async with AsyncSessionFactory() as db:
        today = date.today()
        result = await db.execute(
            select(Debt).where(
                Debt.due_date.is_not(None),
                Debt.due_date < today,
                Debt.status.in_([DebtStatus.ACTIVE, DebtStatus.PARTIALLY_PAID]),
            )
        )
        overdue_debts = list(result.scalars().all())

        for debt in overdue_debts:
            try:
                debt.status = DebtStatus.OVERDUE

                # Receivable → biznes egasiga "sizga qarzdor" eslatmasi yuboriladi.
                # Payable → biznes egasiga "siz qarzdorsiz" eslatmasi yuboriladi.
                # Ikkala holatda ham xabar kompaniya egasiga boradi (mijoz/ta'minotchi
                # tizim foydalanuvchisi emas).
                owner_result = await db.execute(
                    select(User)
                    .join(CompanyUser, CompanyUser.user_id == User.id)
                    .where(CompanyUser.company_id == debt.company_id, CompanyUser.role == "owner")
                )
                owner = owner_result.scalars().first()
                if not owner:
                    continue

                overdue_days = (today - debt.due_date).days
                direction = "sizga qarzdor" if debt.debt_type == DebtType.RECEIVABLE else "sizdan qarzdor"

                await notification_service.send(
                    company_id=str(debt.company_id),
                    user=owner,
                    notification_type="overdue_debt",
                    title="⚠️ Muddati o'tgan qarz",
                    message=(
                        f"{debt.description}: {debt.remaining_amount:,.0f} so'm "
                        f"({overdue_days} kun muddati o'tgan). Kontragent {direction}."
                    ),
                    db=db,
                    data={"debt_id": str(debt.id), "overdue_days": overdue_days},
                )
                notified += 1
            except Exception as e:  # noqa: BLE001
                logger.error(f"Qarz eslatmasi xato (debt={debt.id}): {e}")
                failed += 1

        await db.commit()

    logger.info(f"⏰ Muddati o'tgan qarzlar: {notified} eslatma yuborildi, {failed} xato")
    return {"notified": notified, "failed": failed, "total_overdue": len(overdue_debts)}


async def _send_single_notification(
    company_id: str,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: dict | None,
) -> dict:
    from sqlalchemy import select

    from app.core.database import AsyncSessionFactory
    from app.models.all_models import User
    from app.services.notification.service import NotificationService

    async with AsyncSessionFactory() as db:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return {"status": "skipped", "reason": "Foydalanuvchi topilmadi"}

        notification_service = NotificationService()
        notification = await notification_service.send(
            company_id=company_id,
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            db=db,
            data=data,
        )
        await db.commit()

        return {"status": "sent", "notification_id": str(notification.id), "sent_via": notification.sent_via}
