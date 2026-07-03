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
from app.models.all_models import CompanyUser, Supplier, User

router = APIRouter(prefix="/suppliers")


# ─── Schemas ─────────────────────────────────────────────────────────────────
class SupplierCreate(BaseModel):
    name: str
    inn: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    payment_terms: int = 30


class SupplierUpdate(BaseModel):
    name: str | None = None
    inn: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    payment_terms: int | None = None
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    id: UUID
    name: str
    inn: str | None
    phone: str | None
    email: str | None
    address: str | None
    payment_terms: int
    current_balance: Decimal
    is_active: bool

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.post("/{company_id}", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    company_id: UUID,
    body: SupplierCreate,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.create")),
    db: AsyncSession = Depends(get_db),
):
    supplier = Supplier(company_id=company_id, **body.model_dump())
    db.add(supplier)
    await db.flush()

    await event_bus.emit(Event(
        type=EventType.SUPPLIER_CREATED,
        company_id=company_id,
        user_id=current_user.id,
        data={"supplier_id": str(supplier.id), "name": supplier.name},
    ))

    return supplier


@router.get("/{company_id}", response_model=list[SupplierResponse])
async def list_suppliers(
    company_id: UUID,
    search: str | None = Query(None, description="Ism bo'yicha qidirish"),
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.create")),
    db: AsyncSession = Depends(get_db),
):
    filters = [Supplier.company_id == company_id]
    if not include_inactive:
        filters.append(Supplier.is_active == True)
    if search:
        filters.append(Supplier.name.ilike(f"%{search}%"))

    result = await db.execute(select(Supplier).where(*filters).order_by(Supplier.name))
    return result.scalars().all()


@router.get("/{company_id}/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    company_id: UUID,
    supplier_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.create")),
    db: AsyncSession = Depends(get_db),
):
    return await _get_supplier_or_404(company_id, supplier_id, db)


@router.put("/{company_id}/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    company_id: UUID,
    supplier_id: UUID,
    body: SupplierUpdate,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("transaction.create")),
    db: AsyncSession = Depends(get_db),
):
    supplier = await _get_supplier_or_404(company_id, supplier_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    await db.flush()
    return supplier


async def _get_supplier_or_404(company_id: UUID, supplier_id: UUID, db: AsyncSession) -> Supplier:
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.company_id == company_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Ta'minotchi topilmadi")
    return supplier
