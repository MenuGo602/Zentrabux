"""
Soliq hisob-kitobi background task'lari.

TransactionCreated eventi orqali chaqiriladi — foydalanuvchini
kutdirib qo'ymasdan, soliq hisob-kitobi orqa fonda bajariladi.
"""

from datetime import date
from decimal import Decimal

from loguru import logger

from app.tasks.celery_app import celery_app


@celery_app.task(name="tax.calculate_transaction_tax")
def calculate_tax_task(transaction_id: str, company_id: str) -> dict:
    """
    Bitta tranzaksiya uchun QQS hisoblaydi va tax_calculations
    jadvaliga yozadi. Sinxron Celery task — ichida asyncio.run ishlatadi.
    """
    import asyncio
    return asyncio.run(_calculate_tax_async(transaction_id, company_id))


async def _calculate_tax_async(transaction_id: str, company_id: str) -> dict:
    from sqlalchemy import select

    from app.core.database import AsyncSessionFactory
    from app.engines.tax.uzbekistan import UzbekistanTaxEngine
    from app.models.all_models import Company, TaxCalculation, Transaction

    engine = UzbekistanTaxEngine()

    async with AsyncSessionFactory() as db:
        tx_result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
        transaction = tx_result.scalar_one_or_none()
        if not transaction or transaction.transaction_type != "income":
            return {"status": "skipped", "reason": "Daromad emas yoki topilmadi"}

        company_result = await db.execute(select(Company).where(Company.id == company_id))
        company = company_result.scalar_one_or_none()
        if not company:
            return {"status": "skipped", "reason": "Kompaniya topilmadi"}

        is_vat_payer = company.tax_regime == "QQS"

        vat_result = await engine.calculate_vat(
            taxable_amount=transaction.total_amount,
            company_id=company_id,
            is_vat_payer=is_vat_payer,
        )

        if vat_result:
            tax_calc = TaxCalculation(
                company_id=company_id,
                transaction_id=transaction_id,
                country_code="UZB",
                tax_type=vat_result.tax_type,
                taxable_amount=vat_result.taxable_amount,
                tax_rate=vat_result.rate,
                tax_amount=vat_result.tax_amount,
                period_start=transaction.transaction_date,
                period_end=transaction.transaction_date,
                status="calculated",
            )
            db.add(tax_calc)
            await db.commit()
            logger.info(f"✅ QQS hisoblandi: {vat_result.tax_amount} so'm | tx={transaction_id}")
            return {"status": "calculated", "vat_amount": float(vat_result.tax_amount)}

        return {"status": "skipped", "reason": "QQS to'lovchisi emas"}


@celery_app.task(name="tax.check_deadlines")
def check_tax_deadlines() -> dict:
    """
    Har kuni ishga tushadi (Celery Beat orqali).
    Yaqinlashayotgan soliq muddatlarini tekshiradi va
    bildirishnoma yuborish uchun event chiqaradi.
    """
    import asyncio
    return asyncio.run(_check_deadlines_async())


async def _check_deadlines_async() -> dict:
    from app.engines.tax.uzbekistan import UzbekistanTaxEngine

    engine = UzbekistanTaxEngine()
    today = date.today()
    upcoming = engine.get_upcoming_deadlines(today, days_ahead=7)

    logger.info(f"📅 Yaqin 7 kunda {len(upcoming)} ta soliq muddati bor")

    for entry in upcoming:
        logger.info(f"  → {entry.deadline}: {entry.tax_name} ({entry.period_description})")

    if upcoming:
        await _notify_all_companies_of_deadlines(upcoming, today)

    return {"upcoming_count": len(upcoming)}


async def _notify_all_companies_of_deadlines(upcoming: list, today: date) -> None:
    """Yaqinlashayotgan soliq muddatlari haqida barcha faol kompaniyalarning
    egasi/buxgalterlariga bildirishnoma yuboradi."""
    from sqlalchemy import select

    from app.core.database import AsyncSessionFactory
    from app.models.all_models import Company, CompanyUser, User, UserRole
    from app.services.notification.service import NotificationService

    notification_service = NotificationService()
    message_lines = [f"• {e.deadline}: {e.tax_name} ({e.period_description})" for e in upcoming]
    message = "Yaqinlashayotgan soliq muddatlari:\n" + "\n".join(message_lines)

    async with AsyncSessionFactory() as db:
        companies_result = await db.execute(select(Company.id).where(Company.is_active == True))  # noqa: E712
        company_ids = [row[0] for row in companies_result.all()]

        for company_id in company_ids:
            recipients_result = await db.execute(
                select(User)
                .join(CompanyUser, CompanyUser.user_id == User.id)
                .where(
                    CompanyUser.company_id == company_id,
                    CompanyUser.role.in_([UserRole.OWNER, UserRole.ACCOUNTANT]),
                    User.is_active == True,  # noqa: E712
                )
            )
            for user in recipients_result.scalars().all():
                await notification_service.send(
                    company_id=str(company_id),
                    user=user,
                    notification_type="tax_deadline",
                    title="📅 Soliq muddati yaqinlashmoqda",
                    message=message,
                    db=db,
                )

        await db.commit()
