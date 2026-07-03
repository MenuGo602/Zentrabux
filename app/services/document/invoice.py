"""
Invoice Service — hisob-faktura (schyot-faktura) PDF generatsiyasi.

Bitta Transaction (odatda ``income``, mijozga qarshi) asosida hisob-faktura
tuzadi. QQS to'lovchi bo'lsa, summa ichidan QQS ajratib ko'rsatiladi
(TaxEngine orqali — hech qachon o'zi hisoblamaydi).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.tax.uzbekistan import UzbekistanTaxEngine
from app.models.all_models import Company, Customer, Transaction
from app.services.document.pdf import (
    CompanyInfo,
    DocumentContext,
    PDFBuilder,
    TableColumn,
    format_amount,
)
from app.services.document.qr import generate_document_verification_qr


class InvoiceServiceError(ValueError):
    """Hisob-faktura yaratib bo'lmaganda ko'tariladi (masalan, mijoz topilmadi)."""


class InvoiceService:
    def __init__(self, tax_engine: UzbekistanTaxEngine | None = None) -> None:
        self._tax_engine = tax_engine or UzbekistanTaxEngine()

    async def generate(
        self,
        company_id: str,
        transaction_id: str,
        db: AsyncSession,
        invoice_number: str | None = None,
        include_qr: bool = True,
    ) -> bytes:
        transaction = await self._get_transaction(company_id, transaction_id, db)
        company = await self._get_company(company_id, db)

        customer_name = "Naqd mijoz"
        customer_inn = None
        customer_address = None
        if transaction.customer_id:
            customer = await self._get_customer(transaction.customer_id, db)
            if customer:
                customer_name = customer.name
                customer_inn = customer.inn
                customer_address = customer.address

        invoice_number = invoice_number or transaction.reference_number or str(transaction.id)[:8]
        is_vat_payer = company.tax_regime == "QQS"

        amount = transaction.total_amount
        vat_result = await self._tax_engine.calculate_vat(
            taxable_amount=amount, company_id=company_id, is_vat_payer=is_vat_payer
        )

        columns = [
            TableColumn("№", 10, "center"),
            TableColumn("Tavsif", 95, "left"),
            TableColumn("Summa", 45, "right"),
        ]
        rows = [["1", transaction.description, format_amount(amount, transaction.currency)]]

        totals: list[tuple[str, str]] = []
        if vat_result:
            subtotal = amount - vat_result.tax_amount
            totals.append(("Summa (QQS'siz):", format_amount(subtotal, transaction.currency)))
            totals.append((f"QQS ({vat_result.rate}%):", format_amount(vat_result.tax_amount, transaction.currency)))
        totals.append(("Jami to'lov:", format_amount(amount, transaction.currency)))

        qr_bytes = None
        if include_qr:
            qr_bytes = generate_document_verification_qr(invoice_number, company.inn, amount)

        context = DocumentContext(
            title="HISOB-FAKTURA",
            document_number=invoice_number,
            company=CompanyInfo(
                name=company.name, inn=company.inn, address=company.address,
                phone=company.phone, email=company.email,
            ),
            counterparty_name=customer_name,
            counterparty_inn=customer_inn,
            counterparty_address=customer_address,
            issue_date=str(transaction.transaction_date),
            table_columns=columns,
            table_rows=rows,
            totals=totals,
            footer_note=f"Zentra orqali generatsiya qilindi — {date.today()}",
            qr_image_bytes=qr_bytes,
        )

        return PDFBuilder(context).build()

    async def _get_transaction(self, company_id: str, transaction_id: str, db: AsyncSession) -> Transaction:
        result = await db.execute(
            select(Transaction).where(Transaction.id == transaction_id, Transaction.company_id == company_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise InvoiceServiceError("Tranzaksiya topilmadi")
        return transaction

    async def _get_company(self, company_id: str, db: AsyncSession) -> Company:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            raise InvoiceServiceError("Kompaniya topilmadi")
        return company

    async def _get_customer(self, customer_id, db: AsyncSession) -> Customer | None:
        result = await db.execute(select(Customer).where(Customer.id == customer_id))
        return result.scalar_one_or_none()
