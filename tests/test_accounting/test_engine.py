"""
Accounting Engine testlari.

Bu modul Zentra'ning yuragi bo'lgani uchun har bir
buxgalteriya qoidasi alohida tekshiriladi.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.accounting.engine import (
    AccountingEngine,
    AccountingEntry,
    EntryType,
    JournalLine,
    PaymentMethod,
    TxType,
)
from app.models.all_models import Company


@pytest.fixture
def engine() -> AccountingEngine:
    return AccountingEngine()


class TestValidation:
    """Kiruvchi ma'lumotlar validatsiyasi"""

    async def test_negative_amount_rejected(self, engine: AccountingEngine):
        entry = AccountingEntry(
            transaction_type=TxType.INCOME,
            amount=Decimal("-1000"),
            description="Test",
            transaction_date=date.today(),
        )
        with pytest.raises(ValueError, match="musbat bo'lishi kerak"):
            engine._validate_entry(entry)

    async def test_zero_amount_rejected(self, engine: AccountingEngine):
        entry = AccountingEntry(
            transaction_type=TxType.INCOME,
            amount=Decimal("0"),
            description="Test",
            transaction_date=date.today(),
        )
        with pytest.raises(ValueError):
            engine._validate_entry(entry)

    async def test_empty_description_rejected(self, engine: AccountingEngine):
        entry = AccountingEntry(
            transaction_type=TxType.INCOME,
            amount=Decimal("1000"),
            description="   ",
            transaction_date=date.today(),
        )
        with pytest.raises(ValueError, match="Tavsif bo'sh"):
            engine._validate_entry(entry)

    async def test_invalid_currency_rejected(self, engine: AccountingEngine):
        entry = AccountingEntry(
            transaction_type=TxType.INCOME,
            amount=Decimal("1000"),
            description="Test",
            transaction_date=date.today(),
            currency="XXX",
        )
        with pytest.raises(ValueError, match="Noto'g'ri valyuta"):
            engine._validate_entry(entry)


class TestDoubleEntryBalance:
    """Debit == Credit — buxgalteriya altin qoidasi"""

    def test_balanced_lines_pass(self, engine: AccountingEngine):
        lines = [
            JournalLine("5110", EntryType.DEBIT, Decimal("100000")),
            JournalLine("9010", EntryType.CREDIT, Decimal("100000")),
        ]
        # Xatolik chiqmasligi kerak
        engine._assert_balanced(lines)

    def test_unbalanced_lines_raise(self, engine: AccountingEngine):
        lines = [
            JournalLine("5110", EntryType.DEBIT, Decimal("100000")),
            JournalLine("9010", EntryType.CREDIT, Decimal("99999")),
        ]
        with pytest.raises(ValueError, match="balanssiz"):
            engine._assert_balanced(lines)

    def test_multi_line_balance(self, engine: AccountingEngine):
        """Bir nechta liniya bilan balans tekshiruvi"""
        lines = [
            JournalLine("7110", EntryType.DEBIT, Decimal("60000")),
            JournalLine("7430", EntryType.DEBIT, Decimal("40000")),
            JournalLine("5110", EntryType.CREDIT, Decimal("100000")),
        ]
        engine._assert_balanced(lines)  # Xatolik chiqmasligi kerak


class TestJournalLineBuilding:
    """Tranzaksiya turlariga ko'ra to'g'ri jurnal yozuvlari yaratilishi"""

    def test_income_cash_creates_correct_lines(self, engine: AccountingEngine):
        entry = AccountingEntry(
            transaction_type=TxType.INCOME,
            amount=Decimal("500000"),
            description="Mahsulot sotildi",
            transaction_date=date.today(),
            payment_method=PaymentMethod.CASH,
            is_credit=False,
        )
        lines = engine._build_journal_lines(entry)

        assert len(lines) == 2
        debit_line = next(l for l in lines if l.entry_type == EntryType.DEBIT)
        credit_line = next(l for l in lines if l.entry_type == EntryType.CREDIT)

        assert debit_line.account_code == "5110"   # Kassa
        assert credit_line.account_code == "9010"  # Daromad
        assert debit_line.amount == credit_line.amount == Decimal("500000")

    def test_income_credit_uses_receivables(self, engine: AccountingEngine):
        """Qarzga sotuv → Xaridorlar bilan hisob-kitob schyoti ishlatilishi kerak"""
        entry = AccountingEntry(
            transaction_type=TxType.INCOME,
            amount=Decimal("1000000"),
            description="Qarzga sotuv",
            transaction_date=date.today(),
            is_credit=True,
        )
        lines = engine._build_journal_lines(entry)

        debit_line = next(l for l in lines if l.entry_type == EntryType.DEBIT)
        assert debit_line.account_code == "4010"   # Debitorlik qarz

    def test_expense_bank_creates_correct_lines(self, engine: AccountingEngine):
        entry = AccountingEntry(
            transaction_type=TxType.EXPENSE,
            amount=Decimal("200000"),
            description="Internet to'lovi",
            transaction_date=date.today(),
            payment_method=PaymentMethod.BANK,
        )
        lines = engine._build_journal_lines(entry)

        credit_line = next(l for l in lines if l.entry_type == EntryType.CREDIT)
        assert credit_line.account_code == "5210"  # Bank

    def test_expense_credit_uses_payables(self, engine: AccountingEngine):
        """Qarzga xarid → Ta'minotchilar bilan hisob-kitob schyoti"""
        entry = AccountingEntry(
            transaction_type=TxType.EXPENSE,
            amount=Decimal("3000000"),
            description="Qarzga tovar olindi",
            transaction_date=date.today(),
            is_credit=True,
        )
        lines = engine._build_journal_lines(entry)

        credit_line = next(l for l in lines if l.entry_type == EntryType.CREDIT)
        assert credit_line.account_code == "6010"  # Kreditorlik qarz

    def test_journal_type_requires_manual_lines(self, engine: AccountingEngine):
        entry = AccountingEntry(
            transaction_type=TxType.JOURNAL,
            amount=Decimal("100000"),
            description="Manual yozuv",
            transaction_date=date.today(),
        )
        with pytest.raises(ValueError, match="jurnal liniyalari kerak"):
            engine._build_journal_lines(entry)


class TestFullProcessIntegration:
    """To'liq process() metodini DB bilan tekshirish"""

    async def test_income_transaction_persists_correctly(
        self, engine: AccountingEngine, db_session: AsyncSession, test_company: Company
    ):
        entry = AccountingEntry(
            transaction_type=TxType.INCOME,
            amount=Decimal("750000"),
            description="Xizmat ko'rsatildi",
            transaction_date=date.today(),
            payment_method=PaymentMethod.CASH,
        )

        result = await engine.process(
            entry=entry,
            company_id=str(test_company.id),
            user_id=str(test_company.id),  # demo uchun
            db=db_session,
        )

        assert result["total_amount"] == 750000.0
        assert result["status"] == "confirmed"
        assert len(result["journal_lines"]) == 2

    async def test_credit_income_creates_debt_record(
        self, engine: AccountingEngine, db_session: AsyncSession, test_company: Company
    ):
        from sqlalchemy import select
        from app.models.all_models import Debt, DebtType

        entry = AccountingEntry(
            transaction_type=TxType.INCOME,
            amount=Decimal("2000000"),
            description="Qarzga sotuv — Akmal",
            transaction_date=date.today(),
            is_credit=True,
        )

        result = await engine.process(
            entry=entry,
            company_id=str(test_company.id),
            user_id=str(test_company.id),
            db=db_session,
        )

        debt_result = await db_session.execute(
            select(Debt).where(Debt.transaction_id == result["id"])
        )
        debt = debt_result.scalar_one_or_none()

        assert debt is not None
        assert debt.debt_type == DebtType.RECEIVABLE
        assert debt.original_amount == Decimal("2000000")
        assert debt.remaining_amount == Decimal("2000000")
