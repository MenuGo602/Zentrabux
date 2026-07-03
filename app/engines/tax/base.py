"""
Tax Engine — Base Interface.

Har bir mamlakat o'z modulini shu interfeysga asosan yozadi:
    tax/uzbekistan.py
    tax/kazakhstan.py   (kelajak)
    tax/kyrgyzstan.py   (kelajak)

Prinsip: Tax Engine deterministik bo'lishi shart.
AI hech qachon soliq summasini o'zi hisoblamaydi — faqat
operatsiya turini aniqlaydi, qolganini shu klasslar bajaradi.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class TaxResult:
    tax_type: str              # vat, profit_tax, turnover_tax, social_tax
    tax_name: str               # Inson o'qiy oladigan nom
    taxable_amount: Decimal
    rate: Decimal                # Foizda, masalan 12.00
    tax_amount: Decimal
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "tax_type": self.tax_type,
            "tax_name": self.tax_name,
            "taxable_amount": float(self.taxable_amount),
            "rate_percent": float(self.rate),
            "tax_amount": float(self.tax_amount),
            "notes": self.notes,
        }


@dataclass
class TaxCalendarEntry:
    tax_type: str
    tax_name: str
    deadline: date
    period_description: str    # "2026-yil 1-chorak uchun"
    is_filing: bool = True      # True = deklaratsiya, False = to'lov


class BaseTaxEngine(ABC):
    """Barcha mamlakat soliq dvigatellari shu interfeysni amalga oshiradi"""

    country_code: str
    country_name: str

    @abstractmethod
    async def calculate_vat(
        self, taxable_amount: Decimal, company_id: str, **kwargs
    ) -> TaxResult | None:
        """QQS hisoblash. Agar kompaniya QQS to'lovchisi bo'lmasa None qaytaradi."""
        ...

    @abstractmethod
    async def calculate_profit_tax(
        self, net_profit: Decimal, company_id: str, **kwargs
    ) -> TaxResult | None:
        """Foyda solig'i (yuridik shaxslar uchun)"""
        ...

    @abstractmethod
    async def calculate_turnover_tax(
        self, revenue: Decimal, company_id: str, **kwargs
    ) -> TaxResult | None:
        """Aylanmadan olinadigan soliq (soddalashtirilgan rejim)"""
        ...

    @abstractmethod
    async def calculate_social_tax(
        self, salary_fund: Decimal, company_id: str, **kwargs
    ) -> TaxResult:
        """Ijtimoiy soliq (ish haqi fondidan)"""
        ...

    @abstractmethod
    def get_tax_calendar(self, year: int) -> list[TaxCalendarEntry]:
        """Yillik soliq taqvimi — qachon qaysi deklaratsiya/to'lov"""
        ...

    @abstractmethod
    def determine_regime(self, annual_revenue: Decimal) -> str:
        """Yillik aylanmaga ko'ra qaysi soliq rejimi tegishli ekanini aniqlaydi"""
        ...
