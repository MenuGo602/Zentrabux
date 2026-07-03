from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Company, Customer, Transaction, TransactionStatus, TransactionType
from app.services.document.act import ActService, ActServiceError


class TestActService:
    async def test_generates_valid_pdf_with_customer(
        self, db_session: AsyncSession, test_company: Company
    ):
        customer = Customer(company_id=test_company.id, name="Bek Servis MCHJ", inn="111222333")
        db_session.add(customer)
        await db_session.flush()

        tx = Transaction(
            company_id=test_company.id,
            transaction_date=date.today(),
            description="Konsalting xizmati",
            transaction_type=TransactionType.INCOME,
            total_amount=Decimal("750000"),
            currency="UZS",
            status=TransactionStatus.CONFIRMED,
            customer_id=customer.id,
        )
        db_session.add(tx)
        await db_session.flush()

        service = ActService()
        pdf_bytes = await service.generate(str(test_company.id), str(tx.id), db_session)

        assert pdf_bytes.startswith(b"%PDF")

    async def test_raises_for_missing_transaction(
        self, db_session: AsyncSession, test_company: Company
    ):
        import uuid

        service = ActService()

        with pytest.raises(ActServiceError, match="Tranzaksiya topilmadi"):
            await service.generate(str(test_company.id), str(uuid.uuid4()), db_session)

    async def test_raises_for_missing_company(self, db_session: AsyncSession, test_company: Company):
        import uuid

        tx = Transaction(
            company_id=test_company.id,
            transaction_date=date.today(),
            description="Xizmat",
            transaction_type=TransactionType.INCOME,
            total_amount=Decimal("100000"),
            currency="UZS",
        )
        db_session.add(tx)
        await db_session.flush()

        service = ActService()

        with pytest.raises(ActServiceError, match="Tranzaksiya topilmadi"):
            await service.generate(str(uuid.uuid4()), str(tx.id), db_session)
