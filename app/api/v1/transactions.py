from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.permissions import require_permission
from app.engines.accounting.engine import AccountingEngine, AccountingEntry
from app.events.bus import Event, EventType, event_bus
from app.models.all_models import CompanyUser, Transaction, TransactionType, TransactionStatus, User

router = APIRouter(prefix="/transactions")
accounting_engine = AccountingEngine()


# ─── Schemas ─────────────────────────────────────────────────────────────────
class TransactionCreate(BaseModel):
    transaction_date: date
    description: str
    transaction_type: TransactionType
    total_amount: Decimal
    currency: str = "UZS"
    category_id: UUID | None = None
    customer_id: UUID | None = None
    supplier_id: UUID | None = None
    notes: str | None = None
    # AI tomonidan kelgan bo'lsa
    ai_generated: bool = False
    ai_confidence: Decimal | None = None


class TransactionResponse(BaseModel):
    id: str
    transaction_date: date
    description: str
    transaction_type: str
    total_amount: Decimal
    currency: str
    status: str
    ai_generated: bool
    created_at: str

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.post("/{company_id}", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    company_id: UUID,
    body: TransactionCreate,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Yangi tranzaksiya yaratish.

    Jarayon:
    1. AI (agar AI orqali kelgan bo'lsa) → intent + entity
    2. SHU ENDPOINT → Accounting Engine
    3. Accounting Engine → double-entry + validate
    4. Event → Notification, Tax, Audit
    """
    entry = AccountingEntry(
        transaction_type=body.transaction_type,
        amount=body.total_amount,
        description=body.description,
        category_id=str(body.category_id) if body.category_id else None,
        customer_id=str(body.customer_id) if body.customer_id else None,
        supplier_id=str(body.supplier_id) if body.supplier_id else None,
        transaction_date=body.transaction_date,
        currency=body.currency,
        ai_generated=body.ai_generated,
        ai_confidence=body.ai_confidence,
    )

    result = await accounting_engine.process(
        entry=entry,
        company_id=str(company_id),
        user_id=str(current_user.id),
        db=db,
    )

    # Event chiqarish
    await event_bus.emit(Event(
        type=EventType.TRANSACTION_CREATED,
        company_id=company_id,
        user_id=current_user.id,
        data={
            "transaction_id": result["id"],
            "amount": float(body.total_amount),
            "type": body.transaction_type,
            "description": body.description,
        },
    ))

    return result


@router.get("/{company_id}", response_model=list[TransactionResponse])
async def list_transactions(
    company_id: UUID,
    transaction_type: TransactionType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = [Transaction.company_id == company_id]

    if transaction_type:
        filters.append(Transaction.transaction_type == transaction_type)
    if date_from:
        filters.append(Transaction.transaction_date >= date_from)
    if date_to:
        filters.append(Transaction.transaction_date <= date_to)

    result = await db.execute(
        select(Transaction)
        .where(and_(*filters))
        .order_by(Transaction.transaction_date.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.patch("/{company_id}/{transaction_id}/confirm")
async def confirm_transaction(
    company_id: UUID,
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.confirm")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.company_id == company_id,
            )
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Tranzaksiya topilmadi")

    tx.status = TransactionStatus.CONFIRMED
    tx.approved_by = current_user.id

    return {"status": "confirmed", "id": str(tx.id)}
