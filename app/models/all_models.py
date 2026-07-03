"""
Zentra — SQLAlchemy ORM modellari.
Barcha jadvallar shu faylda.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    DECIMAL,
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ─── Helpers ─────────────────────────────────────────────────────────────────
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# ─── Enums ───────────────────────────────────────────────────────────────────
class UserRole(StrEnum):
    OWNER = "owner"
    ACCOUNTANT = "accountant"
    EMPLOYEE = "employee"


class TransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    JOURNAL = "journal"


class TransactionStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class EntryType(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class DebtType(StrEnum):
    RECEIVABLE = "receivable"   # Bizga qarz
    PAYABLE = "payable"         # Biz qarz


class DebtStatus(StrEnum):
    ACTIVE = "active"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    WRITTEN_OFF = "written_off"


class NotificationChannel(StrEnum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"


class MemoryType(StrEnum):
    RECURRING_EXPENSE = "recurring_expense"
    PREFERRED_CATEGORY = "preferred_category"
    SUPPLIER_PATTERN = "supplier_pattern"
    BEHAVIOR = "behavior"


# ─── Mixin ───────────────────────────────────────────────────────────────────
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )


# ═══════════════════════════════════════════════════════════════════════════════
# USERS & COMPANIES
# ═══════════════════════════════════════════════════════════════════════════════

class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int | None] = mapped_column(unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(5), default="uz")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    company_memberships: Mapped[list["CompanyUser"]] = relationship(back_populates="user")
    ai_conversations: Mapped[list["AIConversation"]] = relationship(back_populates="user")
    ai_memories: Mapped[list["AIMemory"]] = relationship(back_populates="user")


class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255))
    inn: Mapped[str | None] = mapped_column(String(20), unique=True)
    legal_form: Mapped[str | None] = mapped_column(String(50))   # OOO, YAT, AJ
    tax_regime: Mapped[str | None] = mapped_column(String(50))   # QQS, patent
    country_code: Mapped[str] = mapped_column(String(3), default="UZB")
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    fiscal_year_start: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    members: Mapped[list["CompanyUser"]] = relationship(back_populates="company")
    accounts: Mapped[list["Account"]] = relationship(back_populates="company")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="company")
    categories: Mapped[list["Category"]] = relationship(back_populates="company")
    customers: Mapped[list["Customer"]] = relationship(back_populates="company")
    suppliers: Mapped[list["Supplier"]] = relationship(back_populates="company")


class CompanyUser(UUIDMixin, Base):
    __tablename__ = "company_users"
    __table_args__ = (UniqueConstraint("company_id", "user_id"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))  # UserRole
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    company: Mapped["Company"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="company_memberships", foreign_keys=[user_id])


# ═══════════════════════════════════════════════════════════════════════════════
# ACCOUNTING
# ═══════════════════════════════════════════════════════════════════════════════

class Account(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(20))           # 5110, 6010
    name: Mapped[str] = mapped_column(String(255))
    account_type: Mapped[str] = mapped_column(String(20))   # AccountType
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))

    company: Mapped["Company"] = relationship(back_populates="accounts")
    children: Mapped[list["Account"]] = relationship()
    journal_entries: Mapped[list["JournalEntry"]] = relationship(back_populates="account")


class Category(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    category_type: Mapped[str] = mapped_column(String(20))  # income | expense
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id")
    )
    color: Mapped[str | None] = mapped_column(String(7))
    icon: Mapped[str | None] = mapped_column(String(50))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped["Company"] = relationship(back_populates="categories")


class Transaction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "transactions"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(Text)
    reference_number: Mapped[str | None] = mapped_column(String(100))
    transaction_type: Mapped[str] = mapped_column(String(50))   # TransactionType
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("1"))
    status: Mapped[str] = mapped_column(String(20), default=TransactionStatus.PENDING)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    attachments: Mapped[list] = mapped_column(JSON, default=list)

    company: Mapped["Company"] = relationship(back_populates="transactions")
    journal_entries: Mapped[list["JournalEntry"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class JournalEntry(UUIDMixin, Base):
    __tablename__ = "journal_entries"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE")
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    entry_type: Mapped[str] = mapped_column(String(6))     # debit | credit
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    transaction: Mapped["Transaction"] = relationship(back_populates="journal_entries")
    account: Mapped["Account"] = relationship(back_populates="journal_entries")


# ═══════════════════════════════════════════════════════════════════════════════
# COUNTERPARTIES
# ═══════════════════════════════════════════════════════════════════════════════

class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    inn: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    current_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    company: Mapped["Company"] = relationship(back_populates="customers")


class Supplier(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    inn: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    payment_terms: Mapped[int] = mapped_column(Integer, default=30)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    company: Mapped["Company"] = relationship(back_populates="suppliers")


# ═══════════════════════════════════════════════════════════════════════════════
# INVENTORY
# ═══════════════════════════════════════════════════════════════════════════════

class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "products"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    sku: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"))
    unit: Mapped[str | None] = mapped_column(String(50))
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    selling_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    current_stock: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"))
    min_stock: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"))
    max_stock: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    is_service: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryMovement(UUIDMixin, Base):
    __tablename__ = "inventory_movements"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"))
    movement_type: Mapped[str] = mapped_column(String(20))   # in | out | adjustment
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    warehouse: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


# ═══════════════════════════════════════════════════════════════════════════════
# DEBTS
# ═══════════════════════════════════════════════════════════════════════════════

class Debt(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "debts"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"))
    debt_type: Mapped[str] = mapped_column(String(20))       # DebtType
    counterparty_type: Mapped[str | None] = mapped_column(String(20))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    description: Mapped[str] = mapped_column(Text)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default=DebtStatus.ACTIVE)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"))

    payments: Mapped[list["DebtPayment"]] = relationship(back_populates="debt", cascade="all, delete-orphan")


class DebtPayment(UUIDMixin, Base):
    __tablename__ = "debt_payments"

    debt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("debts.id", ondelete="CASCADE"))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    payment_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    debt: Mapped["Debt"] = relationship(back_populates="payments")


# ═══════════════════════════════════════════════════════════════════════════════
# AI
# ═══════════════════════════════════════════════════════════════════════════════

class AIConversation(UUIDMixin, Base):
    __tablename__ = "ai_conversations"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    message_role: Mapped[str] = mapped_column(String(20))   # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(100))
    extracted_data: Mapped[dict | None] = mapped_column(JSON)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"))
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped["User"] = relationship(back_populates="ai_conversations")


class AIMemory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_memory"
    __table_args__ = (UniqueConstraint("company_id", "user_id", "memory_type", "key"),)

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    memory_type: Mapped[str] = mapped_column(String(50))    # MemoryType
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.0"))
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    last_used: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="ai_memories")


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS & AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

class Notification(UUIDMixin, Base):
    __tablename__ = "notifications"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    notification_type: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_via: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"

    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), index=True)
    table_name: Mapped[str | None] = mapped_column(String(100))
    record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    old_values: Mapped[dict | None] = mapped_column(JSON)
    new_values: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


# ═══════════════════════════════════════════════════════════════════════════════
# TAX
# ═══════════════════════════════════════════════════════════════════════════════

class TaxCalculation(UUIDMixin, Base):
    __tablename__ = "tax_calculations"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"))
    country_code: Mapped[str] = mapped_column(String(3))
    tax_type: Mapped[str] = mapped_column(String(50))
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="calculated")
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Report(UUIDMixin, Base):
    __tablename__ = "reports"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    report_type: Mapped[str] = mapped_column(String(50))     # pnl, balance, cashflow, tax
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="generating")
    data: Mapped[dict | None] = mapped_column(JSON)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    ai_analysis: Mapped[str | None] = mapped_column(Text)
    file_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
