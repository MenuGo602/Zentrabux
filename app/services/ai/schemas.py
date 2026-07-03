"""
AI Service — umumiy data sxemalari.

Bu modul AI pipeline bo'ylab (intent → extraction → memory → orchestrator
→ response) uzatiladigan barcha struktura turlarini belgilaydi.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class Intent(StrEnum):
    """AI aniqlay oladigan niyat turlari."""

    CREATE_TRANSACTION = "create_transaction"      # "1 mln so'mga tovar sotdim"
    QUERY_BALANCE = "query_balance"                  # "kassada qancha pul bor?"
    QUERY_DEBT = "query_debt"                        # "kim menga qarzdor?"
    QUERY_REPORT = "query_report"                    # "shu oy foydam qancha?"
    QUERY_TAX = "query_tax"                          # "QQS qancha to'layman?"
    RECORD_DEBT_PAYMENT = "record_debt_payment"       # "Aziz qarzini to'ladi"
    SMALLTALK = "smalltalk"                           # salomlashish va h.k.
    UNKNOWN = "unknown"                               # tushunarsiz xabar


class IntentResult(BaseModel):
    """Intent Detection bosqichining natijasi."""

    intent: Intent
    confidence: Decimal = Field(ge=0, le=1)
    reasoning: str = ""


class ExtractedTransaction(BaseModel):
    """Matn/rasmdan ajratib olingan tranzaksiya ma'lumotlari.

    Hamma maydonlar ixtiyoriy — chunki AI ba'zi narsalarni topa olmasligi
    mumkin. Orchestrator yetishmayotgan muhim maydonlar (masalan amount)
    bo'lsa, foydalanuvchidan qayta so'raydi, hech qachon taxmin qilib
    Accounting Engine'ga yubormaydi.
    """

    transaction_type: str | None = None     # income | expense | transfer
    amount: Decimal | None = None
    currency: str = "UZS"
    description: str | None = None
    category_hint: str | None = None        # AI taklif qilgan kategoriya nomi
    counterparty_name: str | None = None    # mijoz/ta'minotchi ismi (xom matn)
    payment_method: str | None = None       # cash | bank | e_wallet
    is_credit: bool = False                 # qarzga sotuv/xarid
    transaction_date: date | None = None
    confidence: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)


class ExtractedDebtPayment(BaseModel):
    """Qarz to'lovi haqidagi xabardan ajratilgan ma'lumot."""

    counterparty_name: str | None = None
    amount: Decimal | None = None
    payment_date: date | None = None
    confidence: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)


class OCRResult(BaseModel):
    """Chek/faktura rasmidan o'qilgan ma'lumot."""

    raw_text: str = ""
    merchant_name: str | None = None
    total_amount: Decimal | None = None
    currency: str = "UZS"
    purchase_date: date | None = None
    line_items: list[str] = Field(default_factory=list)
    confidence: Decimal = Field(default=Decimal("0"), ge=0, le=1)


class MemorySuggestion(BaseModel):
    """AI Memory'dan kelgan taklif (masalan, doimiy kategoriya moslashtirish)."""

    memory_type: str
    key: str
    value: dict
    confidence: Decimal


class AIResponse(BaseModel):
    """Orchestrator'ning yakuniy natijasi — API javobi sifatida qaytariladi."""

    intent: Intent
    message: str                              # foydalanuvchiga ko'rsatiladigan tabiiy til javobi
    requires_confirmation: bool = False        # AI tasdiqlash so'rayaptimi
    requires_clarification: bool = False       # yetishmayotgan ma'lumot bor
    transaction: dict | None = None            # agar tranzaksiya yaratilgan bo'lsa
    data: dict = Field(default_factory=dict)   # qo'shimcha struktura (hisobot, qarz ro'yxati va h.k.)
    session_id: str | None = None
