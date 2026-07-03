from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.permissions import require_permission
from app.engines.report.trial_balance import TrialBalanceEngine
from app.models.all_models import Account, AccountType, CompanyUser, JournalEntry, Transaction, User

router = APIRouter(prefix="/accounts")
trial_balance_engine = TrialBalanceEngine()


# ─── Schemas ─────────────────────────────────────────────────────────────────
class AccountCreate(BaseModel):
    code: str
    name: str
    account_type: AccountType
    parent_id: UUID | None = None
    currency: str = "UZS"


class AccountUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    parent_id: UUID | None = None


class AccountResponse(BaseModel):
    id: UUID
    code: str
    name: str
    account_type: str
    parent_id: UUID | None
    currency: str
    is_system: bool
    is_active: bool
    balance: Decimal

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.get("/{company_id}", response_model=list[AccountResponse])
async def list_accounts(
    company_id: UUID,
    account_type: AccountType | None = None,
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("account.view")),
    db: AsyncSession = Depends(get_db),
):
    """Kompaniyaning to'liq schyotlar rejasi (Chart of Accounts)."""
    filters = [Account.company_id == company_id]
    if account_type:
        filters.append(Account.account_type == account_type)
    if not include_inactive:
        filters.append(Account.is_active == True)  # noqa: E712

    result = await db.execute(select(Account).where(*filters).order_by(Account.code))
    return result.scalars().all()


@router.get("/{company_id}/trial-balance")
async def get_trial_balance(
    company_id: UUID,
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("account.view")),
    db: AsyncSession = Depends(get_db),
):
    """Aylanma qaydnoma — barcha schyotlarning Debit/Credit aylanmasi va qoldig'i."""
    tb = await trial_balance_engine.generate(str(company_id), db, period_start, period_end)
    return {
        "period_start": str(tb.period_start) if tb.period_start else None,
        "period_end": str(tb.period_end) if tb.period_end else None,
        "is_balanced": tb.is_balanced,
        "total_debit": float(tb.total_debit),
        "total_credit": float(tb.total_credit),
        "lines": [
            {
                "account_code": line.account_code,
                "account_name": line.account_name,
                "account_type": line.account_type,
                "total_debit": float(line.total_debit),
                "total_credit": float(line.total_credit),
                "balance": float(line.balance),
            }
            for line in tb.lines
        ],
    }


@router.get("/{company_id}/{account_id}", response_model=AccountResponse)
async def get_account(
    company_id: UUID,
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("account.view")),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account_or_404(company_id, account_id, db)
    return account


@router.get("/{company_id}/{account_id}/general-ledger")
async def get_general_ledger(
    company_id: UUID,
    account_id: UUID,
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    limit: int = Query(100, le=500),
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("account.view")),
    db: AsyncSession = Depends(get_db),
):
    """Bitta schyot bo'yicha barcha jurnal yozuvlari (general ledger)."""
    account = await _get_account_or_404(company_id, account_id, db)

    filters = [JournalEntry.account_id == account.id]
    query = (
        select(JournalEntry, Transaction)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(*filters)
    )
    if period_start:
        query = query.where(Transaction.transaction_date >= period_start)
    if period_end:
        query = query.where(Transaction.transaction_date <= period_end)

    query = query.order_by(Transaction.transaction_date.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    running_balance = account.balance
    entries = []
    # Eng yangidan eskisiga qarab kelyapmiz — har birini olib tashlab orqaga hisoblaymiz
    for journal_entry, transaction in rows:
        entries.append({
            "transaction_id": str(transaction.id),
            "transaction_date": str(transaction.transaction_date),
            "description": journal_entry.description or transaction.description,
            "entry_type": journal_entry.entry_type,
            "amount": float(journal_entry.amount),
            "balance_after": float(running_balance),
        })
        is_normal_debit = account.account_type in ("asset", "expense")
        is_debit_entry = journal_entry.entry_type == "debit"
        if is_debit_entry == is_normal_debit:
            running_balance -= journal_entry.amount
        else:
            running_balance += journal_entry.amount

    return {
        "account": {"code": account.code, "name": account.name, "balance": float(account.balance)},
        "entries": entries,
    }


@router.post("/{company_id}", response_model=AccountResponse, status_code=201)
async def create_account(
    company_id: UUID,
    body: AccountCreate,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("account.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Yangi (maxsus) schyot qo'shish — standart schyotlar bootstrap orqali yaratiladi."""
    existing = await db.execute(
        select(Account).where(Account.company_id == company_id, Account.code == body.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"'{body.code}' kodli schyot allaqachon mavjud")

    if body.parent_id:
        await _get_account_or_404(company_id, body.parent_id, db)

    account = Account(
        company_id=company_id,
        code=body.code,
        name=body.name,
        account_type=body.account_type,
        parent_id=body.parent_id,
        currency=body.currency,
        is_system=False,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return account


@router.put("/{company_id}/{account_id}", response_model=AccountResponse)
async def update_account(
    company_id: UUID,
    account_id: UUID,
    body: AccountUpdate,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("account.manage")),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account_or_404(company_id, account_id, db)

    if body.name is not None:
        account.name = body.name
    if body.is_active is not None:
        if account.is_system and not body.is_active:
            raise HTTPException(
                status_code=400, detail="Standart (tizim) schyotlarni faolsizlantirib bo'lmaydi"
            )
        account.is_active = body.is_active
    if body.parent_id is not None:
        await _get_account_or_404(company_id, body.parent_id, db)
        account.parent_id = body.parent_id

    await db.flush()
    return account


@router.delete("/{company_id}/{account_id}")
async def delete_account(
    company_id: UUID,
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("account.manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Schyotni o'chiradi.

    Tizim schyotlari (standart Chart of Accounts) hech qachon o'chirilmaydi —
    faqat foydalanuvchi qo'shgan maxsus schyotlar o'chirilishi mumkin, va
    faqat ularda hech qanday jurnal yozuvi bo'lmasa (tarixiy ma'lumot
    yo'qolmasligi uchun).
    """
    account = await _get_account_or_404(company_id, account_id, db)

    if account.is_system:
        raise HTTPException(status_code=400, detail="Standart (tizim) schyotlarni o'chirib bo'lmaydi")

    has_entries = await db.execute(
        select(JournalEntry.id).where(JournalEntry.account_id == account.id).limit(1)
    )
    if has_entries.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Jurnal yozuvlari mavjud schyotni o'chirib bo'lmaydi — uni faolsizlantiring",
        )

    await db.delete(account)
    await db.flush()
    return {"status": "deleted", "id": str(account_id)}


# ─── Yordamchi ────────────────────────────────────────────────────────────────
async def _get_account_or_404(company_id: UUID, account_id: UUID, db: AsyncSession) -> Account:
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.company_id == company_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Schyot topilmadi")
    return account
