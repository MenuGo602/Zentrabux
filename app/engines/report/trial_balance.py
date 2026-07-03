"""
Trial Balance — Aylanma qaydnoma.

Barcha schyotlarning Debit/Credit aylanmalarini va yakuniy
qoldiqlarini ko'rsatadi. Boshqa barcha hisobotlar (P&L, Balance Sheet)
shu yerdan hisoblanadi.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Account, JournalEntry, Transaction, TransactionStatus


@dataclass
class TrialBalanceLine:
    account_code: str
    account_name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal      # Normal balans tomoniga ko'ra musbat


@dataclass
class TrialBalance:
    company_id: str
    period_start: date | None
    period_end: date | None
    lines: list[TrialBalanceLine]
    total_debit: Decimal
    total_credit: Decimal

    @property
    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit


class TrialBalanceEngine:
    """Aylanma qaydnomani hisoblaydi — barcha hisobotlarning poydevori"""

    async def generate(
        self,
        company_id: str,
        db: AsyncSession,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> TrialBalance:
        filters = [
            Account.company_id == company_id,
            Transaction.status == TransactionStatus.CONFIRMED,
        ]
        if period_start:
            filters.append(Transaction.transaction_date >= period_start)
        if period_end:
            filters.append(Transaction.transaction_date <= period_end)

        query = (
            select(
                Account.code,
                Account.name,
                Account.account_type,
                func.coalesce(
                    func.sum(JournalEntry.amount).filter(JournalEntry.entry_type == "debit"), 0
                ).label("total_debit"),
                func.coalesce(
                    func.sum(JournalEntry.amount).filter(JournalEntry.entry_type == "credit"), 0
                ).label("total_credit"),
            )
            .select_from(Account)
            .join(JournalEntry, JournalEntry.account_id == Account.id)
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .where(and_(*filters))
            .group_by(Account.code, Account.name, Account.account_type)
            .order_by(Account.code)
        )

        result = await db.execute(query)
        rows = result.all()

        lines: list[TrialBalanceLine] = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")

        for row in rows:
            debit = Decimal(str(row.total_debit))
            credit = Decimal(str(row.total_credit))

            # Normal balans hisoblash: aktiv/xarajat = Debit-Credit, qolganlari = Credit-Debit
            if row.account_type in ("asset", "expense"):
                balance = debit - credit
            else:
                balance = credit - debit

            lines.append(
                TrialBalanceLine(
                    account_code=row.code,
                    account_name=row.name,
                    account_type=row.account_type,
                    total_debit=debit,
                    total_credit=credit,
                    balance=balance,
                )
            )
            total_debit += debit
            total_credit += credit

        return TrialBalance(
            company_id=company_id,
            period_start=period_start,
            period_end=period_end,
            lines=lines,
            total_debit=total_debit,
            total_credit=total_credit,
        )
