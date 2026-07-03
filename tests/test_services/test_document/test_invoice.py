from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Company, Customer, Transaction, TransactionStatus, TransactionType
from app.services.document.invoice import InvoiceService, InvoiceServiceError


async def _make_income_transaction(
    db: AsyncSession, company: Company, customer: Customer | None = None, amount: str = "500000"
) -> Transaction:
    tx = Transaction(
        company_id=company.id,
        transaction_date=date.today(),
        description="Tovar sotuvi",
        transaction_type=TransactionType.INCOME,
        total_amount=Decimal(amount),
        currency="UZS",
        status=TransactionStatus.CONFIRMED,
        customer_id=customer.id if customer else None,
    )
    db.add(tx)
    await db.flush()
    return tx


class TestInvoiceService:
    async def test_generates_valid_pdf_for_non_vat_payer(
        self, db_session: AsyncSession, test_company: Company
    ):
        customer = Customer(company_id=test_company.id, name="Aziz Karimov", inn="987654321")
        db_session.add(customer)
        await db_session.flush()
        tx = await _make_income_transaction(db_session, test_company, customer)

        service = InvoiceService()
        pdf_bytes = await service.generate(str(test_company.id), str(tx.id), db_session)

        assert pdf_bytes.startswith(b"%PDF")

    async def test_generates_valid_pdf_for_vat_payer_with_vat_breakdown(
        self, db_session: AsyncSession, test_company: Company
    ):
        test_company.tax_regime = "QQS"
        tx = await _make_income_transaction(db_session, test_company)

        service = InvoiceService()
        pdf_bytes = await service.generate(str(test_company.id), str(tx.id), db_session)

        assert pdf_bytes.startswith(b"%PDF")

    async def test_generates_pdf_without_customer_falls_back_to_cash_customer(
        self, db_session: AsyncSession, test_company: Company
    ):
        tx = await _make_income_transaction(db_session, test_company, customer=None)

        service = InvoiceService()
        pdf_bytes = await service.generate(str(test_company.id), str(tx.id), db_session)

        assert pdf_bytes.startswith(b"%PDF")

    async def test_raises_for_missing_transaction(
        self, db_session: AsyncSession, test_company: Company
    ):
        import uuid

        service = InvoiceService()

        with pytest.raises(InvoiceServiceError, match="Tranzaksiya topilmadi"):
            await service.generate(str(test_company.id), str(uuid.uuid4()), db_session)

    async def test_uses_custom_invoice_number_when_provided(
        self, db_session: AsyncSession, test_company: Company
    ):
        tx = await _make_income_transaction(db_session, test_company)
        service = InvoiceService()

        pdf_bytes = await service.generate(
            str(test_company.id), str(tx.id), db_session, invoice_number="CUSTOM-123"
        )

        assert pdf_bytes.startswith(b"%PDF")
