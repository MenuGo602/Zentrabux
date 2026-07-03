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
from app.engines.accounting.engine import PaymentMethod
from app.events.bus import Event, EventType, event_bus
from app.models.all_models import CompanyUser, Customer, Debt, DebtStatus, DebtType, Supplier, User
from app.services.debt import DebtService, DebtServiceError

router = APIRouter(prefix="/debts")
debt_service = DebtService()


# ─── Schemas ─────────────────────────────────────────────────────────────────
class DebtCreate(BaseModel):
    debt_type: DebtType
    customer_id: UUID | None = None
    supplier_id: UUID | None = None
    description: str
    original_amount: Decimal
    due_date: date | None = None
    interest_rate: Decimal = Decimal("0")


class DebtResponse(BaseModel):
    id: UUID
    debt_type: str
    customer_id: UUID | None
    supplier_id: UUID | None
    description: str
    original_amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal
    due_date: date | None
    status: str

    class Config:
        from_attributes = True


class DebtPaymentRequest(BaseModel):
    amount: Decimal
    payment_date: date | None = None
    payment_method: PaymentMethod = PaymentMethod.CASH
    notes: str | None = None


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.get("/{company_id}", response_model=list[DebtResponse])
async def list_debts(
    company_id: UUID,
    debt_type: DebtType | None = None,
    status_filter: DebtStatus | None = Query(None, alias="status"),
    limit: int = Query(100, le=500),
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("debt.view")),
    db: AsyncSession = Depends(get_db),
):
    filters = [Debt.company_id == company_id]
    if debt_type:
        filters.append(Debt.debt_type == debt_type)
    if status_filter:
        filters.append(Debt.status == status_filter)

    result = await db.execute(
        select(Debt)
        .where(*filters)
        .order_by(Debt.due_date.asc().nulls_last(), Debt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/{company_id}/overdue", response_model=list[DebtResponse])
async def list_overdue_debts(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("debt.view")),
    db: AsyncSession = Depends(get_db),
):
    """Muddati o'tgan, hali to'liq yopilmagan qarzlar."""
    today = date.today()
    result = await db.execute(
        select(Debt).where(
            Debt.company_id == company_id,
            Debt.due_date.is_not(None),
            Debt.due_date < today,
            Debt.status.in_([DebtStatus.ACTIVE, DebtStatus.PARTIALLY_PAID]),
        ).order_by(Debt.due_date.asc())
    )
    debts = list(result.scalars().all())

    # Status'ni real vaqtda OVERDUE'ga yangilab qo'yamiz (lazy update)
    for debt in debts:
        if debt.status != DebtStatus.OVERDUE:
            debt.status = DebtStatus.OVERDUE
    if debts:
        await db.flush()

    return debts


@router.get("/{company_id}/aging")
async def get_aging_report(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("debt.view")),
    db: AsyncSession = Depends(get_db),
):
    """
    Qarzlarni muddati o'tgan kunlar bo'yicha guruhlaydi
    (current / 1-30 / 31-60 / 61-90 / 90+) — moliyaviy nazorat uchun.
    """
    result = await db.execute(
        select(Debt).where(
            Debt.company_id == company_id,
            Debt.status.in_([DebtStatus.ACTIVE, DebtStatus.PARTIALLY_PAID, DebtStatus.OVERDUE]),
        )
    )
    debts = list(result.scalars().all())

    buckets: dict[str, dict[str, Decimal]] = {
        bucket: {"receivable": Decimal("0"), "payable": Decimal("0")}
        for bucket in ("current", "1-30", "31-60", "61-90", "90+")
    }

    for debt in debts:
        bucket = debt_service.aging_bucket(debt)
        key = "receivable" if debt.debt_type == DebtType.RECEIVABLE else "payable"
        buckets[bucket][key] += debt.remaining_amount

    return {
        "as_of": str(date.today()),
        "buckets": {
            bucket: {"receivable": float(v["receivable"]), "payable": float(v["payable"])}
            for bucket, v in buckets.items()
        },
    }


@router.get("/{company_id}/{debt_id}", response_model=DebtResponse)
async def get_debt(
    company_id: UUID,
    debt_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("debt.view")),
    db: AsyncSession = Depends(get_db),
):
    return await _get_debt_or_404(company_id, debt_id, db)


@router.post("/{company_id}", response_model=DebtResponse, status_code=201)
async def create_debt(
    company_id: UUID,
    body: DebtCreate,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("debt.manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Qarzni qo'lda qayd etish — masalan, boshlang'ich qoldiq (opening balance)
    yoki tranzaksiyaga bog'lanmagan qarz uchun.

    Eslatma: oddiy qarzga sotuv/xarid odatda
    POST /transactions orqali avtomatik yaratiladi (AccountingEngine).
    """
    if body.debt_type == DebtType.RECEIVABLE and not body.customer_id:
        raise HTTPException(status_code=400, detail="Receivable qarz uchun customer_id kerak")
    if body.debt_type == DebtType.PAYABLE and not body.supplier_id:
        raise HTTPException(status_code=400, detail="Payable qarz uchun supplier_id kerak")

    if body.customer_id:
        result = await db.execute(
            select(Customer).where(Customer.id == body.customer_id, Customer.company_id == company_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Mijoz topilmadi")

    if body.supplier_id:
        result = await db.execute(
            select(Supplier).where(Supplier.id == body.supplier_id, Supplier.company_id == company_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Ta'minotchi topilmadi")

    if body.original_amount <= 0:
        raise HTTPException(status_code=400, detail="Qarz summasi musbat bo'lishi kerak")

    debt = Debt(
        company_id=company_id,
        debt_type=body.debt_type,
        counterparty_type="customer" if body.debt_type == DebtType.RECEIVABLE else "supplier",
        customer_id=body.customer_id,
        supplier_id=body.supplier_id,
        description=body.description,
        original_amount=body.original_amount,
        paid_amount=Decimal("0"),
        remaining_amount=body.original_amount,
        due_date=body.due_date,
        interest_rate=body.interest_rate,
        status=DebtStatus.ACTIVE,
    )
    db.add(debt)
    await db.flush()

    await event_bus.emit(Event(
        type=EventType.DEBT_CREATED,
        company_id=company_id,
        user_id=current_user.id,
        data={"debt_id": str(debt.id), "amount": float(body.original_amount), "type": body.debt_type},
    ))

    return debt


@router.post("/{company_id}/{debt_id}/payment")
async def record_debt_payment(
    company_id: UUID,
    debt_id: UUID,
    body: DebtPaymentRequest,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("debt.manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Qarz bo'yicha to'lov qabul qiladi/amalga oshiradi.

    Ichkarida AccountingEngine orqali pul harakati jurnal yozuvi ham
    yaratiladi — Debt jadvali hech qachon yolg'iz o'zgartirilmaydi.
    """
    debt = await _get_debt_or_404(company_id, debt_id, db)

    try:
        result = await debt_service.record_payment(
            debt=debt,
            amount=body.amount,
            company_id=str(company_id),
            user_id=str(current_user.id),
            db=db,
            payment_date=body.payment_date,
            payment_method=body.payment_method,
            notes=body.notes,
        )
    except DebtServiceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await event_bus.emit(Event(
        type=EventType.DEBT_PAYMENT_RECEIVED,
        company_id=company_id,
        user_id=current_user.id,
        data=result,
    ))

    return result


# ─── Yordamchi ────────────────────────────────────────────────────────────────
async def _get_debt_or_404(company_id: UUID, debt_id: UUID, db: AsyncSession) -> Debt:
    result = await db.execute(select(Debt).where(Debt.id == debt_id, Debt.company_id == company_id))
    debt = result.scalar_one_or_none()
    if not debt:
        raise HTTPException(status_code=404, detail="Qarz topilmadi")
    return debt
