from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.permissions import require_permission
from app.events.bus import Event, EventType, event_bus
from app.models.all_models import CompanyUser, Customer, User

router = APIRouter(prefix="/customers")


# ─── Schemas ─────────────────────────────────────────────────────────────────
class CustomerCreate(BaseModel):
    name: str
    inn: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    credit_limit: Decimal = Decimal("0")
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    inn: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    credit_limit: Decimal | None = None
    notes: str | None = None
    is_active: bool | None = None


class CustomerResponse(BaseModel):
    id: UUID
    name: str
    inn: str | None
    phone: str | None
    email: str | None
    address: str | None
    credit_limit: Decimal
    current_balance: Decimal
    is_active: bool

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────
# Ruxsat: "transaction.create" ishlatiladi (Owner/Accountant/Employee — hammasi
# ega), chunki mijoz odatda aynan tranzaksiya/qarz kiritish jarayonida
# yaratiladi ("yangi mijozga sotdim" holatlari uchun alohida "customer.manage"
# ruxsati kiritish ortiqcha bo'lardi).
@router.post("/{company_id}", response_model=CustomerResponse, status_code=201)
async def create_customer(
    company_id: UUID,
    body: CustomerCreate,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.create")),
    db: AsyncSession = Depends(get_db),
):
    customer = Customer(company_id=company_id, **body.model_dump())
    db.add(customer)
    await db.flush()

    await event_bus.emit(Event(
        type=EventType.CUSTOMER_CREATED,
        company_id=company_id,
        user_id=current_user.id,
        data={"customer_id": str(customer.id), "name": customer.name},
    ))

    return customer


@router.get("/{company_id}", response_model=list[CustomerResponse])
async def list_customers(
    company_id: UUID,
    search: str | None = Query(None, description="Ism bo'yicha qidirish"),
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.create")),
    db: AsyncSession = Depends(get_db),
):
    filters = [Customer.company_id == company_id]
    if not include_inactive:
        filters.append(Customer.is_active == True)
    if search:
        filters.append(Customer.name.ilike(f"%{search}%"))

    result = await db.execute(select(Customer).where(*filters).order_by(Customer.name))
    return result.scalars().all()


@router.get("/{company_id}/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    company_id: UUID,
    customer_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.create")),
    db: AsyncSession = Depends(get_db),
):
    return await _get_customer_or_404(company_id, customer_id, db)


@router.put("/{company_id}/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    company_id: UUID,
    customer_id: UUID,
    body: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.create")),
    db: AsyncSession = Depends(get_db),
):
    customer = await _get_customer_or_404(company_id, customer_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await db.flush()
    return customer


async def _get_customer_or_404(company_id: UUID, customer_id: UUID, db: AsyncSession) -> Customer:
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.company_id == company_id)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    return customer
