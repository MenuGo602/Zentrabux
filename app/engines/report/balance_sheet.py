"""
Balance Sheet (Buxgalteriya balansi).

Asosiy tenglama:
    Aktivlar = Majburiyatlar + Kapital

Muayyan sananing holatini ko'rsatadi (davr emas).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.report.trial_balance import TrialBalanceEngine


@dataclass
class BalanceSheetLineItem:
    account_code: str
    account_name: str
    amount: Decimal


@dataclass
class BalanceSheet:
    company_id: str
    as_of_date: date | None
    assets: list[BalanceSheetLineItem] = field(default_factory=list)
    liabilities: list[BalanceSheetLineItem] = field(default_factory=list)
    equity: list[BalanceSheetLineItem] = field(default_factory=list)
    net_profit_current: Decimal = Decimal("0")   # Joriy davr foydasi (kapitalga qo'shiladi)

    @property
    def total_assets(self) -> Decimal:
        return sum((i.amount for i in self.assets), Decimal("0"))

    @property
    def total_liabilities(self) -> Decimal:
        return sum((i.amount for i in self.liabilities), Decimal("0"))

    @property
    def total_equity(self) -> Decimal:
        return sum((i.amount for i in self.equity), Decimal("0")) + self.net_profit_current

    @property
    def is_balanced(self) -> bool:
        """Aktivlar = Majburiyatlar + Kapital tekshiruvi"""
        return self.total_assets == (self.total_liabilities + self.total_equity)

    def to_dict(self) -> dict:
        return {
            "as_of_date": str(self.as_of_date) if self.as_of_date else None,
            "assets": {
                "items": [
                    {"code": i.account_code, "name": i.account_name, "amount": float(i.amount)}
                    for i in self.assets
                ],
                "total": float(self.total_assets),
            },
            "liabilities": {
                "items": [
                    {"code": i.account_code, "name": i.account_name, "amount": float(i.amount)}
                    for i in self.liabilities
                ],
                "total": float(self.total_liabilities),
            },
            "equity": {
                "items": [
                    {"code": i.account_code, "name": i.account_name, "amount": float(i.amount)}
                    for i in self.equity
                ],
                "net_profit_current_period": float(self.net_profit_current),
                "total": float(self.total_equity),
            },
            "is_balanced": self.is_balanced,
        }


class BalanceSheetEngine:
    def __init__(self) -> None:
        self.trial_balance_engine = TrialBalanceEngine()

    async def generate(
        self,
        company_id: str,
        db: AsyncSession,
        as_of_date: date | None = None,
    ) -> BalanceSheet:
        # Balance Sheet — bu hisobotning "boshidan shu sanagacha" bo'lgan holati
        tb = await self.trial_balance_engine.generate(
            company_id, db, period_start=None, period_end=as_of_date
        )

        sheet = BalanceSheet(company_id=company_id, as_of_date=as_of_date)

        for line in tb.lines:
            item = BalanceSheetLineItem(line.account_code, line.account_name, line.balance)

            if line.account_type == "asset" and line.balance != 0:
                sheet.assets.append(item)
            elif line.account_type == "liability" and line.balance != 0:
                sheet.liabilities.append(item)
            elif line.account_type == "equity" and line.balance != 0:
                sheet.equity.append(item)

        # Joriy davr foyda/zararini hisoblash (income - expense) → kapitalga qo'shiladi
        income_total = sum(
            (l.balance for l in tb.lines if l.account_type == "income"), Decimal("0")
        )
        expense_total = sum(
            (l.balance for l in tb.lines if l.account_type == "expense"), Decimal("0")
        )
        sheet.net_profit_current = income_total - expense_total

        return sheet
