"""
Accounting Engine — Zentra'ning yuragi.

Prinsiplar:
✅ Barcha buxgalteriya operatsiyalari shu yerdan o'tadi
✅ Double-entry: Debit == Credit har doim tekshiriladi
✅ Atomic: ya hammasi yoziladi, ya hech narsa
❌ AI bu klassga bevosita yozmaydi
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.all_models import Account, JournalEntry, Transaction, TransactionStatus


# ─── Types ───────────────────────────────────────────────────────────────────
class EntryType(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class TxType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    JOURNAL = "journal"


@dataclass
class JournalLine:
    account_code: str
    entry_type: EntryType
    amount: Decimal
    description: str = ""


class PaymentMethod(StrEnum):
    CASH = "cash"           # Kassa
    BANK = "bank"            # Bank hisobi
    E_WALLET = "e_wallet"     # Click/Payme


@dataclass
class AccountingEntry:
    """
    AI bu strukturani to'ldiradi → Engine bajaradi.
    AI hech qachon jurnal yozuvlarini o'zi yaratmaydi.
    """
    transaction_type: TxType
    amount: Decimal
    description: str
    transaction_date: date
    category_id: str | None = None
    customer_id: str | None = None
    supplier_id: str | None = None
    currency: str = "UZS"
    exchange_rate: Decimal = Decimal("1")
    payment_method: PaymentMethod = PaymentMethod.CASH
    is_credit: bool = False          # Qarzga sotuv/xarid (kontragent schyoti ishlatiladi)
    notes: str | None = None
    reference_number: str | None = None
    ai_generated: bool = False
    ai_confidence: Decimal | None = None
    # Engine bu maydonni o'zi to'ldiradi
    journal_lines: list[JournalLine] = field(default_factory=list)


# ─── Chart of Accounts (O'zbekiston standart) ────────────────────────────────
class ChartOfAccounts:
    """
    O'zbekiston Moliya Vazirligi buyrug'i bo'yicha
    standart schyotlar rejasi.
    """
    # Aktivlar
    CASH_UZS       = "5110"  # Kassa (UZS)
    CASH_USD       = "5120"  # Kassa (USD)
    BANK_UZS       = "5210"  # Bank hisobi (UZS)
    BANK_USD       = "5220"  # Bank hisobi (USD)
    ACCOUNTS_RECV  = "4010"  # Debitorlik qarz
    INVENTORY      = "2910"  # Tovar-moddiy boyliklar
    FIXED_ASSETS   = "0110"  # Asosiy vositalar

    # Majburiyatlar
    ACCOUNTS_PAY   = "6010"  # Kreditorlik qarz
    TAX_PAYABLE    = "6410"  # Soliq majburiyatlari
    SALARY_PAY     = "6710"  # Ish haqi

    # Kapital
    CHARTER_CAP    = "8330"  # Ustav kapitali
    RETAINED_EARN  = "8710"  # Taqsimlanmagan foyda

    # Daromad
    SALES_REV      = "9010"  # Asosiy faoliyatdan daromad
    OTHER_REV      = "9310"  # Boshqa daromadlar

    # Xarajat
    COGS           = "2010"  # Sotilgan tovar tannarxi
    SALARY_EXP     = "7110"  # Mehnat haqi xarajati
    RENT_EXP       = "7420"  # Ijara xarajati
    UTIL_EXP       = "7430"  # Kommunal xarajatlar
    OTHER_EXP      = "9430"  # Boshqa xarajatlar


COA = ChartOfAccounts()


# ─── Accounting Engine ───────────────────────────────────────────────────────
class AccountingEngine:
    """
    Barcha buxgalteriya operatsiyalari shu sinf orqali o'tadi.

    Ishlatish:
        engine = AccountingEngine()
        result = await engine.process(entry, company_id, user_id, db)
    """

    async def process(
        self,
        entry: AccountingEntry,
        company_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> dict:
        logger.info(
            f"AccountingEngine.process: {entry.transaction_type} "
            f"{entry.amount} {entry.currency}"
        )

        # 1. Kiruvchi ma'lumotlarni tekshirish
        self._validate_entry(entry)

        # 2. Double-entry jurnal yozuvlarini yaratish
        lines = self._build_journal_lines(entry)

        # 3. Debit == Credit tekshirish (buxgalteriya altın qoidasi)
        self._assert_balanced(lines)

        # 4. Atomic yozish
        transaction = await self._persist(entry, lines, company_id, user_id, db)

        # 5. Hisoblar balansini yangilash
        await self._update_account_balances(lines, company_id, db)

        logger.info(f"✅ Tranzaksiya yaratildi: {transaction.id}")

        return {
            "id": str(transaction.id),
            "transaction_date": str(transaction.transaction_date),
            "description": transaction.description,
            "transaction_type": transaction.transaction_type,
            "total_amount": float(transaction.total_amount),
            "currency": transaction.currency,
            "status": transaction.status,
            "ai_generated": transaction.ai_generated,
            "created_at": str(transaction.created_at),
            "journal_lines": [
                {
                    "account_code": line.account_code,
                    "entry_type": line.entry_type,
                    "amount": float(line.amount),
                }
                for line in lines
            ],
        }

    # ─── Validation ──────────────────────────────────────────────────────────
    def _validate_entry(self, entry: AccountingEntry) -> None:
        if entry.amount <= 0:
            raise ValueError(f"Summa musbat bo'lishi kerak: {entry.amount}")
        if not entry.description.strip():
            raise ValueError("Tavsif bo'sh bo'lishi mumkin emas")
        if entry.currency not in ("UZS", "USD", "EUR", "RUB"):
            raise ValueError(f"Noto'g'ri valyuta: {entry.currency}")

    # ─── Build Journal Lines ──────────────────────────────────────────────────
    def _build_journal_lines(self, entry: AccountingEntry) -> list[JournalLine]:
        """
        Har bir tranzaksiya turi uchun double-entry yozuvlarini yaratish.

        Buxgalteriya qoidasi:
        - Daromad (naqd): Kassa/Bank (Debit) ↔ Daromad schyoti (Credit)
        - Daromad (qarzga): Xaridorlar bilan hisob (Debit) ↔ Daromad schyoti (Credit)
        - Xarajat (naqd): Xarajat schyoti (Debit) ↔ Kassa/Bank (Credit)
        - Xarajat (qarzga): Xarajat schyoti (Debit) ↔ Ta'minotchilar hisobi (Credit)
        """
        cash_account = self._resolve_payment_account(entry.payment_method)

        match entry.transaction_type:
            case TxType.INCOME:
                debit_account = COA.ACCOUNTS_RECV if entry.is_credit else cash_account
                debit_desc = "Xaridor qarzi" if entry.is_credit else "Kassa/Bank kirim"
                return [
                    JournalLine(debit_account, EntryType.DEBIT, entry.amount, debit_desc),
                    JournalLine(COA.SALES_REV, EntryType.CREDIT, entry.amount, entry.description),
                ]

            case TxType.EXPENSE:
                credit_account = COA.ACCOUNTS_PAY if entry.is_credit else cash_account
                credit_desc = "Ta'minotchi qarzi" if entry.is_credit else "Kassa/Bank chiqim"
                return [
                    JournalLine(COA.OTHER_EXP, EntryType.DEBIT, entry.amount, entry.description),
                    JournalLine(credit_account, EntryType.CREDIT, entry.amount, credit_desc),
                ]

            case TxType.TRANSFER:
                return [
                    JournalLine(COA.BANK_UZS, EntryType.DEBIT, entry.amount, "Transfer kirim"),
                    JournalLine(COA.CASH_UZS, EntryType.CREDIT, entry.amount, "Transfer chiqim"),
                ]

            case TxType.JOURNAL:
                if not entry.journal_lines:
                    raise ValueError("Journal tranzaksiyasi uchun jurnal liniyalari kerak")
                return entry.journal_lines

            case _:
                raise ValueError(f"Noma'lum tranzaksiya turi: {entry.transaction_type}")

    def _resolve_payment_account(self, method: PaymentMethod) -> str:
        return {
            PaymentMethod.CASH: COA.CASH_UZS,
            PaymentMethod.BANK: COA.BANK_UZS,
            PaymentMethod.E_WALLET: "5510",
        }[method]

    # ─── Balance Check ────────────────────────────────────────────────────────
    def _assert_balanced(self, lines: list[JournalLine]) -> None:
        """Buxgalteriya altın qoidasi: ΣDebit == ΣCredit"""
        total_debit = sum(
            line.amount for line in lines if line.entry_type == EntryType.DEBIT
        )
        total_credit = sum(
            line.amount for line in lines if line.entry_type == EntryType.CREDIT
        )

        if total_debit != total_credit:
            raise ValueError(
                f"❌ Jurnal balanssiz: "
                f"Debit {total_debit:,.2f} ≠ Credit {total_credit:,.2f}"
            )

        logger.debug(f"✅ Balans tekshirildi: {total_debit:,.2f}")

    # ─── Persist ──────────────────────────────────────────────────────────────
    async def _persist(
        self,
        entry: AccountingEntry,
        lines: list[JournalLine],
        company_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> Transaction:
        """Atomic: Transaction + JournalEntries birga yoziladi"""

        # Transaction yaratish
        transaction = Transaction(
            company_id=company_id,
            transaction_date=entry.transaction_date,
            description=entry.description,
            transaction_type=entry.transaction_type,
            total_amount=entry.amount,
            currency=entry.currency,
            exchange_rate=entry.exchange_rate,
            status=TransactionStatus.CONFIRMED,
            created_by=user_id,
            category_id=entry.category_id,
            customer_id=entry.customer_id,
            supplier_id=entry.supplier_id,
            ai_generated=entry.ai_generated,
            ai_confidence=entry.ai_confidence,
            notes=entry.notes,
            reference_number=entry.reference_number,
        )
        db.add(transaction)
        await db.flush()  # ID olish uchun

        # Jurnal yozuvlarini yaratish
        for line in lines:
            # Schyot kodini topish
            account_result = await db.execute(
                select(Account).where(
                    Account.company_id == company_id,
                    Account.code == line.account_code,
                    Account.is_active == True,
                )
            )
            account = account_result.scalar_one_or_none()

            if not account:
                logger.warning(f"Schyot topilmadi: {line.account_code}, avto-o'tkazish")
                # Production'da bu xato bo'lishi kerak
                # Hozircha davom etamiz (demo uchun)

            journal_entry = JournalEntry(
                transaction_id=transaction.id,
                account_id=account.id if account else None,
                entry_type=line.entry_type,
                amount=line.amount,
                description=line.description,
            )
            db.add(journal_entry)

        await db.flush()

        # Qarzga sotuv/xarid bo'lsa — avtomatik Debt yozuvi
        if entry.is_credit:
            await self._create_debt_record(entry, transaction, db)

        return transaction

    async def _create_debt_record(
        self,
        entry: "AccountingEntry",
        transaction: Transaction,
        db: AsyncSession,
    ) -> None:
        """Qarzga operatsiya bo'lsa, debts jadvaliga avtomatik yozuv kiritadi"""
        from app.models.all_models import Debt, DebtStatus, DebtType

        if entry.transaction_type == TxType.INCOME:
            debt_type = DebtType.RECEIVABLE   # Bizga qarz (xaridor)
            counterparty_type = "customer"
        elif entry.transaction_type == TxType.EXPENSE:
            debt_type = DebtType.PAYABLE      # Biz qarz (ta'minotchi)
            counterparty_type = "supplier"
        else:
            return

        debt = Debt(
            company_id=transaction.company_id,
            debt_type=debt_type,
            counterparty_type=counterparty_type,
            customer_id=entry.customer_id,
            supplier_id=entry.supplier_id,
            description=entry.description,
            original_amount=entry.amount,
            paid_amount=Decimal("0"),
            remaining_amount=entry.amount,
            status=DebtStatus.ACTIVE,
            transaction_id=transaction.id,
        )
        db.add(debt)
        await db.flush()
        logger.info(f"✅ Qarz yozuvi yaratildi: {debt.id} ({debt_type})")

    # ─── Update Balances ──────────────────────────────────────────────────────
    async def _update_account_balances(
        self,
        lines: list[JournalLine],
        company_id: str,
        db: AsyncSession,
    ) -> None:
        """Schyotlar balansini yangilash"""
        for line in lines:
            result = await db.execute(
                select(Account).where(
                    Account.company_id == company_id,
                    Account.code == line.account_code,
                )
            )
            account = result.scalar_one_or_none()
            if not account:
                continue

            # Normal balans: Aktiv schyotlar uchun Debit musbat
            if account.account_type in ("asset", "expense"):
                if line.entry_type == EntryType.DEBIT:
                    account.balance += line.amount
                else:
                    account.balance -= line.amount
            else:  # liability, equity, income
                if line.entry_type == EntryType.CREDIT:
                    account.balance += line.amount
                else:
                    account.balance -= line.amount
