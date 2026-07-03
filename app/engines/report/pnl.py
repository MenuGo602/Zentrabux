"""
Profit & Loss (Foyda va Zarar hisoboti).

Trial Balance asosida hisoblanadi:
  Daromad - Xarajat = Sof foyda/zarar
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.report.trial_balance import TrialBalanceEngine


@dataclass
class PnLLineItem:
    account_code: str
    account_name: str
    amount: Decimal


@dataclass
class ProfitAndLoss:
    company_id: str
    period_start: date | None
    period_end: date | None
    income_items: list[PnLLineItem] = field(default_factory=list)
    expense_items: list[PnLLineItem] = field(default_factory=list)

    @property
    def total_income(self) -> Decimal:
        return sum((item.amount for item in self.income_items), Decimal("0"))

    @property
    def total_expense(self) -> Decimal:
        return sum((item.amount for item in self.expense_items), Decimal("0"))

    @property
    def net_profit(self) -> Decimal:
        return self.total_income - self.total_expense

    @property
    def profit_margin(self) -> Decimal:
        """Foyda marjasi foizda"""
        if self.total_income == 0:
            return Decimal("0")
        return (self.net_profit / self.total_income) * 100

    def to_dict(self) -> dict:
        return {
            "period_start": str(self.period_start) if self.period_start else None,
            "period_end": str(self.period_end) if self.period_end else None,
            "income": {
                "items": [
                    {"code": i.account_code, "name": i.account_name, "amount": float(i.amount)}
                    for i in self.income_items
                ],
                "total": float(self.total_income),
            },
            "expense": {
                "items": [
                    {"code": i.account_code, "name": i.account_name, "amount": float(i.amount)}
                    for i in self.expense_items
                ],
                "total": float(self.total_expense),
            },
            "net_profit": float(self.net_profit),
            "profit_margin_percent": float(round(self.profit_margin, 2)),
        }


class ProfitAndLossEngine:
    def __init__(self) -> None:
        self.trial_balance_engine = TrialBalanceEngine()

    async def generate(
        self,
        company_id: str,
        db: AsyncSession,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> ProfitAndLoss:
        tb = await self.trial_balance_engine.generate(
            company_id, db, period_start, period_end
        )

        pnl = ProfitAndLoss(
            company_id=company_id,
            period_start=period_start,
            period_end=period_end,
        )

        for line in tb.lines:
            if line.account_type == "income" and line.balance != 0:
                pnl.income_items.append(
                    PnLLineItem(line.account_code, line.account_name, line.balance)
                )
            elif line.account_type == "expense" and line.balance != 0:
                pnl.expense_items.append(
                    PnLLineItem(line.account_code, line.account_name, line.balance)
                )

        return pnl
