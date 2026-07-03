"""
Hisobot generatsiyasi background task'lari.

Celery Beat orqali har hafta/oyda barcha faol kompaniyalar uchun
P&L hisobotini tayyorlaydi va egasi/buxgalterlariga bildirishnoma
sifatida yuboradi. Og'ir hisoblash ishi (ko'plab tranzaksiyalarni
yig'ish) foydalanuvchini kutdirmasligi uchun orqa fonda bajariladi.
"""

from __future__ import annotations

from datetime import date, timedelta

from loguru import logger

from app.tasks.celery_app import celery_app


@celery_app.task(name="reports.generate_weekly_reports")
def generate_weekly_reports() -> dict:
    """Har dushanba barcha faol kompaniyalar uchun haftalik P&L hisobotini yuboradi."""
    import asyncio

    today = date.today()
    period_start = today - timedelta(days=7)
    return asyncio.run(_generate_reports_for_all_companies(period_start, today, "weekly"))


@celery_app.task(name="reports.generate_monthly_reports")
def generate_monthly_reports() -> dict:
    """Har oyning 1-sanasida o'tgan oy uchun P&L hisobotini yuboradi."""
    import asyncio

    today = date.today()
    last_day_prev_month = today.replace(day=1) - timedelta(days=1)
    period_start = last_day_prev_month.replace(day=1)
    return asyncio.run(_generate_reports_for_all_companies(period_start, last_day_prev_month, "monthly"))


@celery_app.task(name="reports.generate_company_report")
def generate_company_report_task(company_id: str, period_start_iso: str, period_end_iso: str) -> dict:
    """Bitta kompaniya uchun P&L hisobotini generatsiya qiladi (qo'lda ham chaqirilishi mumkin)."""
    import asyncio

    period_start = date.fromisoformat(period_start_iso)
    period_end = date.fromisoformat(period_end_iso)
    return asyncio.run(_generate_and_notify(company_id, period_start, period_end, "manual"))


async def _generate_reports_for_all_companies(period_start: date, period_end: date, kind: str) -> dict:
    from sqlalchemy import select

    from app.core.database import AsyncSessionFactory
    from app.models.all_models import Company

    generated = 0
    failed = 0

    async with AsyncSessionFactory() as db:
        result = await db.execute(select(Company.id).where(Company.is_active == True))  # noqa: E712
        company_ids = [row[0] for row in result.all()]

    for company_id in company_ids:
        try:
            async with AsyncSessionFactory() as db:
                await _generate_and_notify(str(company_id), period_start, period_end, kind, db)
            generated += 1
        except Exception as e:  # noqa: BLE001 — bitta kompaniya xatosi boshqalarni to'xtatmasin
            logger.error(f"Hisobot generatsiyasi xato (company={company_id}): {e}")
            failed += 1

    logger.info(f"📊 {kind} hisobotlar: {generated} muvaffaqiyatli, {failed} xato")
    return {"generated": generated, "failed": failed, "kind": kind}


async def _generate_and_notify(
    company_id: str,
    period_start: date,
    period_end: date,
    kind: str,
    db=None,
) -> dict:
    from sqlalchemy import select

    from app.core.database import AsyncSessionFactory
    from app.engines.report.pnl import ProfitAndLossEngine
    from app.models.all_models import Company, CompanyUser, User, UserRole
    from app.services.notification.service import NotificationService

    owns_session = db is None
    if owns_session:
        db = AsyncSessionFactory()

    try:
        pnl_engine = ProfitAndLossEngine()
        notification_service = NotificationService()

        company_result = await db.execute(select(Company).where(Company.id == company_id))
        company = company_result.scalar_one_or_none()
        if not company:
            return {"status": "skipped", "reason": "Kompaniya topilmadi"}

        pnl = await pnl_engine.generate(company_id, db, period_start, period_end)

        title = f"{company.name}: {kind} moliyaviy hisobot"
        message = (
            f"{period_start} — {period_end} davri uchun:\n"
            f"Daromad: {pnl.total_income:,.0f} so'm\n"
            f"Xarajat: {pnl.total_expense:,.0f} so'm\n"
            f"Sof foyda: {pnl.net_profit:,.0f} so'm"
        )

        recipients_result = await db.execute(
            select(User)
            .join(CompanyUser, CompanyUser.user_id == User.id)
            .where(
                CompanyUser.company_id == company_id,
                CompanyUser.role.in_([UserRole.OWNER, UserRole.ACCOUNTANT]),
                User.is_active == True,  # noqa: E712
            )
        )
        recipients = list(recipients_result.scalars().all())

        for user in recipients:
            await notification_service.send(
                company_id=str(company_id),
                user=user,
                notification_type="financial_report",
                title=title,
                message=message,
                db=db,
                data={"net_profit": float(pnl.net_profit), "period_start": str(period_start),
                      "period_end": str(period_end)},
            )

        if owns_session:
            await db.commit()

        return {"status": "sent", "recipients": len(recipients), "net_profit": float(pnl.net_profit)}
    finally:
        if owns_session:
            await db.close()
