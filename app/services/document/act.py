"""
Act Service — Bajarilgan ishlar/xizmatlar dalolatnomasi (Akt) PDF generatsiyasi.

Xizmat/ish sotuvi tranzaksiyasidan so'ng, ikki tomon imzolashi uchun
rasmiy hujjat. Hisob-fakturadan farqi — bu to'lov emas, balki
xizmat/ish BAJARILGANLIGINI tasdiqlaydi.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Company, Customer, Transaction
from app.services.document.pdf import CompanyInfo, DocumentContext, PDFBuilder, TableColumn, format_amount


class ActServiceError(ValueError):
    """Akt yaratib bo'lmaganda ko'tariladi."""


class ActService:
    async def generate(
        self,
        company_id: str,
        transaction_id: str,
        db: AsyncSession,
        act_number: str | None = None,
    ) -> bytes:
        transaction = await self._get_transaction(company_id, transaction_id, db)
        company = await self._get_company(company_id, db)

        customer_name = "Mijoz"
        customer_inn = None
        customer_address = None
        if transaction.customer_id:
            result = await db.execute(select(Customer).where(Customer.id == transaction.customer_id))
            customer = result.scalar_one_or_none()
            if customer:
                customer_name = customer.name
                customer_inn = customer.inn
                customer_address = customer.address

        act_number = act_number or transaction.reference_number or str(transaction.id)[:8]

        columns = [
            TableColumn("№", 10, "center"),
            TableColumn("Xizmat/ish nomi", 95, "left"),
            TableColumn("Summa", 45, "right"),
        ]
        rows = [["1", transaction.description, format_amount(transaction.total_amount, transaction.currency)]]

        body = [
            (
                f"Biz, quyida imzo qo'yuvchilar, \"{company.name}\" (bir tomondan) va "
                f"\"{customer_name}\" (ikkinchi tomondan) ushbu Aktni quyidagilar haqida "
                f"tuzdik: yuqorida ko'rsatilgan xizmat/ish to'liq va sifatli bajarildi, "
                f"tomonlar bir-biriga da'vosi yo'q."
            ),
        ]

        context = DocumentContext(
            title="BAJARILGAN ISHLAR (XIZMATLAR) DALOLATNOMASI",
            document_number=act_number,
            company=CompanyInfo(
                name=company.name, inn=company.inn, address=company.address,
                phone=company.phone, email=company.email,
            ),
            counterparty_name=customer_name,
            counterparty_inn=customer_inn,
            counterparty_address=customer_address,
            issue_date=str(transaction.transaction_date),
            body_paragraphs=body,
            table_columns=columns,
            table_rows=rows,
            totals=[("Jami:", format_amount(transaction.total_amount, transaction.currency))],
            footer_note=f"Zentra orqali generatsiya qilindi — {date.today()}. Ikkala tomon imzosi talab qilinadi.",
        )

        return PDFBuilder(context).build()

    async def _get_transaction(self, company_id: str, transaction_id: str, db: AsyncSession) -> Transaction:
        result = await db.execute(
            select(Transaction).where(Transaction.id == transaction_id, Transaction.company_id == company_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise ActServiceError("Tranzaksiya topilmadi")
        return transaction

    async def _get_company(self, company_id: str, db: AsyncSession) -> Company:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            raise ActServiceError("Kompaniya topilmadi")
        return company
