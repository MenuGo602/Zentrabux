"""
Debt Service — qarzlar bilan ishlash uchun umumiy biznes mantiq.

Bu servis ``api/v1/debts.py`` (HTTP) va AI Orchestrator (chat orqali
"Aziz qarzini to'ladi" kabi xabarlar) tomonidan bab-baravar ishlatiladi —
shu bilan ikkala yo'l ham bir xil qoidalarga rioya qilishini kafolatlaydi.

Muhim: qarz to'lovi har doim pul harakati ham demakdir, shuning uchun
har bir to'lov AccountingEngine orqali jurnal yozuvi sifatida ham
qayd etiladi (Debt jadvali yolg'iz o'zgartirilmaydi).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.accounting.engine import (
    COA,
    AccountingEngine,
    AccountingEntry,
    EntryType,
    JournalLine,
    PaymentMethod,
    TxType,
)
from app.models.all_models import Customer, Debt, DebtPayment, DebtStatus, DebtType, Supplier


class DebtServiceError(ValueError):
    """Qarz operatsiyasida foydalanuvchi xatosi (masalan, ortiqcha to'lov)."""


class DebtService:
    def __init__(self, accounting_engine: AccountingEngine | None = None) -> None:
        self._accounting_engine = accounting_engine or AccountingEngine()

    # ─── Qidiruv ─────────────────────────────────────────────────────────────
    async def find_open_debt_by_counterparty_name(
        self,
        company_id: str,
        counterparty_name: str,
        db: AsyncSession,
    ) -> Debt | None:
        """
        Kontragent ismi bo'yicha eng so'nggi yopilmagan qarzni topadi.
        AI Orchestrator erkin matndan kelgan ismni shu yerda Customer/Supplier
        bilan moslashtiradi (qisman moslik, katta-kichik harf farqisiz).
        """
        name_pattern = f"%{counterparty_name.strip()}%"

        customer_ids_result = await db.execute(
            select(Customer.id).where(
                Customer.company_id == company_id, Customer.name.ilike(name_pattern)
            )
        )
        customer_ids = [row[0] for row in customer_ids_result.all()]

        supplier_ids_result = await db.execute(
            select(Supplier.id).where(
                Supplier.company_id == company_id, Supplier.name.ilike(name_pattern)
            )
        )
        supplier_ids = [row[0] for row in supplier_ids_result.all()]

        if not customer_ids and not supplier_ids:
            return None

        filters = [
            Debt.company_id == company_id,
            Debt.status.in_([DebtStatus.ACTIVE, DebtStatus.PARTIALLY_PAID, DebtStatus.OVERDUE]),
        ]
        match_filters = []
        if customer_ids:
            match_filters.append(Debt.customer_id.in_(customer_ids))
        if supplier_ids:
            match_filters.append(Debt.supplier_id.in_(supplier_ids))
        filters.append(or_(*match_filters))

        result = await db.execute(
            select(Debt).where(*filters).order_by(Debt.due_date.asc().nulls_last(), Debt.created_at.asc())
        )
        return result.scalars().first()

    # ─── To'lov ──────────────────────────────────────────────────────────────
    async def record_payment(
        self,
        debt: Debt,
        amount: Decimal,
        company_id: str,
        user_id: str,
        db: AsyncSession,
        payment_date: date | None = None,
        payment_method: PaymentMethod = PaymentMethod.CASH,
        notes: str | None = None,
    ) -> dict:
        """
        Qarz to'lovini qayd etadi:
            1. Summani tekshiradi (0 < amount <= remaining_amount)
            2. AccountingEngine orqali pul harakati jurnal yozuvini yaratadi
            3. Debt.paid_amount / remaining_amount / status'ni yangilaydi
            4. DebtPayment yozuvini saqlaydi
        """
        if amount <= 0:
            raise DebtServiceError(f"To'lov summasi musbat bo'lishi kerak: {amount}")
        if amount > debt.remaining_amount:
            raise DebtServiceError(
                f"To'lov summasi qoldiq qarzdan ko'p: {amount} > {debt.remaining_amount}"
            )

        payment_date = payment_date or date.today()
        cash_account = self._resolve_payment_account(payment_method)

        if debt.debt_type == DebtType.RECEIVABLE:
            # Mijoz bizga to'lamoqda: Kassa/Bank (Debit) ↔ Xaridorlar hisobi (Credit)
            journal_lines = [
                JournalLine(cash_account, EntryType.DEBIT, amount, "Qarz to'lovi qabul qilindi"),
                JournalLine(COA.ACCOUNTS_RECV, EntryType.CREDIT, amount, debt.description),
            ]
            description = f"Qarz to'lovi qabul qilindi: {debt.description}"
        else:
            # Biz ta'minotchiga to'lamoqdamiz: Ta'minotchilar hisobi (Debit) ↔ Kassa/Bank (Credit)
            journal_lines = [
                JournalLine(COA.ACCOUNTS_PAY, EntryType.DEBIT, amount, debt.description),
                JournalLine(cash_account, EntryType.CREDIT, amount, "Qarz to'lovi amalga oshirildi"),
            ]
            description = f"Qarz to'lovi amalga oshirildi: {debt.description}"

        entry = AccountingEntry(
            transaction_type=TxType.JOURNAL,
            amount=amount,
            description=description,
            transaction_date=payment_date,
            customer_id=str(debt.customer_id) if debt.customer_id else None,
            supplier_id=str(debt.supplier_id) if debt.supplier_id else None,
            payment_method=payment_method,
            notes=notes,
            journal_lines=journal_lines,
        )

        tx_result = await self._accounting_engine.process(
            entry=entry, company_id=company_id, user_id=user_id, db=db
        )

        debt.paid_amount += amount
        debt.remaining_amount -= amount
        debt.status = DebtStatus.PAID if debt.remaining_amount == 0 else DebtStatus.PARTIALLY_PAID

        debt_payment = DebtPayment(
            debt_id=debt.id,
            transaction_id=tx_result["id"],
            amount=amount,
            payment_date=payment_date,
            notes=notes,
        )
        db.add(debt_payment)
        await db.flush()

        return {
            "debt_id": str(debt.id),
            "payment_id": str(debt_payment.id),
            "amount": float(amount),
            "remaining_amount": float(debt.remaining_amount),
            "status": debt.status,
            "transaction_id": tx_result["id"],
        }

    @staticmethod
    def _resolve_payment_account(method: PaymentMethod) -> str:
        return {
            PaymentMethod.CASH: COA.CASH_UZS,
            PaymentMethod.BANK: COA.BANK_UZS,
            PaymentMethod.E_WALLET: "5510",
        }[method]

    # ─── Aging / hisobotlar ─────────────────────────────────────────────────
    @staticmethod
    def aging_bucket(debt: Debt, as_of: date | None = None) -> str:
        """Muddati o'tgan kunlar bo'yicha qarzni guruhlaydi (aging report uchun)."""
        as_of = as_of or date.today()
        if not debt.due_date or debt.due_date >= as_of:
            return "current"
        overdue_days = (as_of - debt.due_date).days
        if overdue_days <= 30:
            return "1-30"
        if overdue_days <= 60:
            return "31-60"
        if overdue_days <= 90:
            return "61-90"
        return "90+"
