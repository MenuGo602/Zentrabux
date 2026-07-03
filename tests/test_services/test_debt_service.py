"""DebtService testlari — to'lov qabul qilish, qidiruv, aging."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Company, Customer, Debt, DebtStatus, DebtType, Supplier, User
from app.services.debt import DebtService, DebtServiceError


async def _make_user(db: AsyncSession) -> User:
    user = User(full_name="Test Buxgalter", phone="+998901234567")
    db.add(user)
    await db.flush()
    return user


async def _make_receivable_debt(
    db: AsyncSession, company: Company, customer_name: str = "Aziz Karimov", amount: str = "500000"
) -> Debt:
    customer = Customer(company_id=company.id, name=customer_name)
    db.add(customer)
    await db.flush()

    debt = Debt(
        company_id=company.id,
        debt_type=DebtType.RECEIVABLE,
        counterparty_type="customer",
        customer_id=customer.id,
        description="Tovar qarzga sotildi",
        original_amount=Decimal(amount),
        paid_amount=Decimal("0"),
        remaining_amount=Decimal(amount),
        status=DebtStatus.ACTIVE,
    )
    db.add(debt)
    await db.flush()
    return debt


class TestRecordPayment:
    async def test_partial_payment_updates_remaining_and_status(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        debt = await _make_receivable_debt(db_session, test_company)
        service = DebtService()

        result = await service.record_payment(
            debt=debt,
            amount=Decimal("200000"),
            company_id=str(test_company.id),
            user_id=str(user.id),
            db=db_session,
        )

        assert result["remaining_amount"] == 300000.0
        assert debt.status == DebtStatus.PARTIALLY_PAID
        assert debt.paid_amount == Decimal("200000")

    async def test_full_payment_marks_as_paid(self, db_session: AsyncSession, test_company: Company):
        user = await _make_user(db_session)
        debt = await _make_receivable_debt(db_session, test_company, amount="100000")
        service = DebtService()

        await service.record_payment(
            debt=debt,
            amount=Decimal("100000"),
            company_id=str(test_company.id),
            user_id=str(user.id),
            db=db_session,
        )

        assert debt.status == DebtStatus.PAID
        assert debt.remaining_amount == Decimal("0")

    async def test_overpayment_is_rejected(self, db_session: AsyncSession, test_company: Company):
        user = await _make_user(db_session)
        debt = await _make_receivable_debt(db_session, test_company, amount="100000")
        service = DebtService()

        with pytest.raises(DebtServiceError, match="ko'p"):
            await service.record_payment(
                debt=debt,
                amount=Decimal("150000"),
                company_id=str(test_company.id),
                user_id=str(user.id),
                db=db_session,
            )

    async def test_zero_or_negative_payment_is_rejected(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        debt = await _make_receivable_debt(db_session, test_company)
        service = DebtService()

        with pytest.raises(DebtServiceError, match="musbat"):
            await service.record_payment(
                debt=debt,
                amount=Decimal("0"),
                company_id=str(test_company.id),
                user_id=str(user.id),
                db=db_session,
            )

    async def test_payable_payment_creates_transaction_reference(
        self, db_session: AsyncSession, test_company: Company
    ):
        user = await _make_user(db_session)
        supplier = Supplier(company_id=test_company.id, name="Ta'minotchi MCHJ")
        db_session.add(supplier)
        await db_session.flush()

        debt = Debt(
            company_id=test_company.id,
            debt_type=DebtType.PAYABLE,
            counterparty_type="supplier",
            supplier_id=supplier.id,
            description="Xom ashyo qarzga olindi",
            original_amount=Decimal("300000"),
            paid_amount=Decimal("0"),
            remaining_amount=Decimal("300000"),
            status=DebtStatus.ACTIVE,
        )
        db_session.add(debt)
        await db_session.flush()

        service = DebtService()
        result = await service.record_payment(
            debt=debt,
            amount=Decimal("300000"),
            company_id=str(test_company.id),
            user_id=str(user.id),
            db=db_session,
        )

        assert result["transaction_id"] is not None
        assert debt.status == DebtStatus.PAID


class TestFindByCounterpartyName:
    async def test_finds_debt_by_partial_case_insensitive_name(
        self, db_session: AsyncSession, test_company: Company
    ):
        await _make_receivable_debt(db_session, test_company, customer_name="Aziz Karimov")
        service = DebtService()

        found = await service.find_open_debt_by_counterparty_name(
            str(test_company.id), "aziz", db_session
        )

        assert found is not None
        assert found.description == "Tovar qarzga sotildi"

    async def test_returns_none_when_no_match(self, db_session: AsyncSession, test_company: Company):
        service = DebtService()

        found = await service.find_open_debt_by_counterparty_name(
            str(test_company.id), "Mavjud Emas", db_session
        )

        assert found is None


class TestAgingBucket:
    def test_no_due_date_is_current(self):
        debt = Debt(remaining_amount=Decimal("1000"))
        assert DebtService.aging_bucket(debt) == "current"

    def test_overdue_15_days_is_1_30_bucket(self):
        debt = Debt(remaining_amount=Decimal("1000"), due_date=date.today() - timedelta(days=15))
        assert DebtService.aging_bucket(debt) == "1-30"

    def test_overdue_100_days_is_90_plus_bucket(self):
        debt = Debt(remaining_amount=Decimal("1000"), due_date=date.today() - timedelta(days=100))
        assert DebtService.aging_bucket(debt) == "90+"
