"""
Cash Flow Statement (Pul oqimi hisoboti).

To'g'ridan-to'g'ri (direct) usul: faqat kassa/bank schyotlari
orqali o'tgan haqiqiy pul harakatlarini ko'rsatadi.

Uch bo'lim:
- Operatsion faoliyat (asosiy biznes)
- Investitsion faoliyat (asosiy vositalar)
- Moliyaviy faoliyat (kreditlar, ustav kapitali)
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Account, JournalEntry, Transaction, TransactionStatus

CASH_ACCOUNT_CODES = {"5110", "5120", "5210", "5220", "5510"}

# Qaysi schyotlar qaysi faoliyat turiga tegishli
INVESTING_CODES = {"0110", "0210", "0410"}          # Asosiy vositalar, nomoddiy aktivlar
FINANCING_CODES = {"8330"}                           # Ustav kapitali, kreditlar


@dataclass
class CashFlowLine:
    description: str
    amount: Decimal


@dataclass
class CashFlowStatement:
    company_id: str
    period_start: date | None
    period_end: date | None
    operating: list[CashFlowLine] = field(default_factory=list)
    investing: list[CashFlowLine] = field(default_factory=list)
    financing: list[CashFlowLine] = field(default_factory=list)
    opening_balance: Decimal = Decimal("0")

    @property
    def operating_total(self) -> Decimal:
        return sum((i.amount for i in self.operating), Decimal("0"))

    @property
    def investing_total(self) -> Decimal:
        return sum((i.amount for i in self.investing), Decimal("0"))

    @property
    def financing_total(self) -> Decimal:
        return sum((i.amount for i in self.financing), Decimal("0"))

    @property
    def net_change(self) -> Decimal:
        return self.operating_total + self.investing_total + self.financing_total

    @property
    def closing_balance(self) -> Decimal:
        return self.opening_balance + self.net_change

    def to_dict(self) -> dict:
        return {
            "period_start": str(self.period_start) if self.period_start else None,
            "period_end": str(self.period_end) if self.period_end else None,
            "opening_balance": float(self.opening_balance),
            "operating": {
                "items": [{"description": i.description, "amount": float(i.amount)} for i in self.operating],
                "total": float(self.operating_total),
            },
            "investing": {
                "items": [{"description": i.description, "amount": float(i.amount)} for i in self.investing],
                "total": float(self.investing_total),
            },
            "financing": {
                "items": [{"description": i.description, "amount": float(i.amount)} for i in self.financing],
                "total": float(self.financing_total),
            },
            "net_change": float(self.net_change),
            "closing_balance": float(self.closing_balance),
        }


class CashFlowEngine:
    """
    Pul oqimini Transaction + JournalEntry orqali to'g'ridan-to'g'ri
    hisoblaydi (kassa/bank schyotlariga tegishli yozuvlar).
    """

    async def generate(
        self,
        company_id: str,
        db: AsyncSession,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> CashFlowStatement:
        statement = CashFlowStatement(
            company_id=company_id,
            period_start=period_start,
            period_end=period_end,
        )

        # Davr boshidagi kassa qoldig'i
        if period_start:
            statement.opening_balance = await self._get_cash_balance_as_of(
                company_id, db, before_date=period_start
            )

        # Davr ichidagi barcha kassa/bank harakatlari
        filters = [
            Account.company_id == company_id,
            Account.code.in_(CASH_ACCOUNT_CODES),
            Transaction.status == TransactionStatus.CONFIRMED,
        ]
        if period_start:
            filters.append(Transaction.transaction_date >= period_start)
        if period_end:
            filters.append(Transaction.transaction_date <= period_end)

        query = (
            select(
                JournalEntry.entry_type,
                JournalEntry.amount,
                JournalEntry.description,
                Transaction.description.label("tx_description"),
            )
            .select_from(JournalEntry)
            .join(Account, Account.id == JournalEntry.account_id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(and_(*filters))
            .order_by(Transaction.transaction_date)
        )

        result = await db.execute(query)
        rows = result.all()

        for row in rows:
            # Kassaga kirim = Debit (musbat pul oqimi)
            # Kassadan chiqim = Credit (manfiy pul oqimi)
            signed_amount = row.amount if row.entry_type == "debit" else -row.amount

            line = CashFlowLine(
                description=row.tx_description or row.description or "Operatsiya",
                amount=signed_amount,
            )

            # Hozircha sodda heuristika: hamma narsa Operating'ga tushadi
            # Keyinroq Investing/Financing aniqlash logikasi qo'shiladi
            statement.operating.append(line)

        return statement

    async def _get_cash_balance_as_of(
        self, company_id: str, db: AsyncSession, before_date: date
    ) -> Decimal:
        """Berilgan sanagacha bo'lgan kassa qoldig'ini hisoblash"""
        query = (
            select(JournalEntry.entry_type, JournalEntry.amount)
            .select_from(JournalEntry)
            .join(Account, Account.id == JournalEntry.account_id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(
                and_(
                    Account.company_id == company_id,
                    Account.code.in_(CASH_ACCOUNT_CODES),
                    Transaction.transaction_date < before_date,
                    Transaction.status == TransactionStatus.CONFIRMED,
                )
            )
        )
        result = await db.execute(query)
        balance = Decimal("0")
        for entry_type, amount in result.all():
            balance += amount if entry_type == "debit" else -amount
        return balance
