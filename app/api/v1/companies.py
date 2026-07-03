from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.engines.accounting.chart_of_accounts import bootstrap_company_accounts
from app.events.bus import Event, EventType, event_bus
from app.models.all_models import Company, CompanyUser, User, UserRole

router = APIRouter(prefix="/companies")


class CompanyCreate(BaseModel):
    name: str
    inn: str | None = None
    legal_form: str | None = None
    tax_regime: str | None = None
    phone: str | None = None
    address: str | None = None


class CompanyResponse(BaseModel):
    id: str
    name: str
    inn: str | None
    legal_form: str | None
    tax_regime: str | None
    currency: str

    class Config:
        from_attributes = True


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    body: CompanyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Yangi kompaniya yaratish.

    Avtomatik ravishda:
    1. Foydalanuvchi Owner sifatida biriktiriladi
    2. Standart Chart of Accounts (40+ schyot) yaratiladi
    """
    company = Company(
        name=body.name,
        inn=body.inn,
        legal_form=body.legal_form,
        tax_regime=body.tax_regime,
        phone=body.phone,
        address=body.address,
        country_code="UZB",
        currency="UZS",
    )
    db.add(company)
    await db.flush()

    # Owner sifatida biriktirish
    membership = CompanyUser(
        company_id=company.id,
        user_id=current_user.id,
        role=UserRole.OWNER,
    )
    db.add(membership)

    # Chart of Accounts bootstrap
    accounts_created = await bootstrap_company_accounts(str(company.id), db)

    await event_bus.emit(Event(
        type=EventType.COMPANY_CREATED,
        company_id=company.id,
        user_id=current_user.id,
        data={"name": company.name, "accounts_created": accounts_created},
    ))

    return company


@router.get("", response_model=list[CompanyResponse])
async def list_my_companies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Company)
        .join(CompanyUser, CompanyUser.company_id == Company.id)
        .where(CompanyUser.user_id == current_user.id, CompanyUser.is_active == True)
    )
    return result.scalars().all()


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Kompaniya topilmadi")
    return company
