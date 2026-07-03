"""
Rol-asoslangan ruxsat tizimi.

Owner    → hamma narsaga ruxsat
Accountant → tranzaksiya, hisobot, qarzlar — lekin xodim/sozlama yo'q
Employee → faqat tranzaksiya qo'shish (o'zi yaratgan)
"""

from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.all_models import CompanyUser, User, UserRole

# Har bir rol uchun ruxsat etilgan harakatlar
ROLE_PERMISSIONS: dict[str, set[str]] = {
    UserRole.OWNER: {
        "transaction.create", "transaction.confirm", "transaction.delete",
        "report.view", "debt.manage", "debt.view", "employee.manage",
        "company.settings", "ai.chat", "account.view", "account.manage",
        "document.generate",
    },
    UserRole.ACCOUNTANT: {
        "transaction.create", "transaction.confirm",
        "report.view", "debt.manage", "debt.view", "ai.chat",
        "account.view", "account.manage", "document.generate",
    },
    UserRole.EMPLOYEE: {
        "transaction.create", "ai.chat", "account.view", "debt.view",
        "document.generate",
    },
}


async def get_company_membership(
    company_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyUser:
    """Foydalanuvchining shu kompaniyadagi a'zoligini tekshiradi"""
    result = await db.execute(
        select(CompanyUser).where(
            CompanyUser.company_id == company_id,
            CompanyUser.user_id == current_user.id,
            CompanyUser.is_active == True,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu kompaniyaga a'zo emassiz",
        )
    return membership


def require_permission(permission: str):
    """
    Dependency factory: kerakli ruxsatni tekshiradi.

    Ishlatish:
        @router.post("/{company_id}/transactions")
        async def create_tx(
            membership: CompanyUser = Depends(require_permission("transaction.create")),
        ):
            ...
    """
    async def checker(
        membership: CompanyUser = Depends(get_company_membership),
    ) -> CompanyUser:
        allowed = ROLE_PERMISSIONS.get(membership.role, set())
        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sizning rolingiz ({membership.role}) bu amalga ruxsat bermaydi: {permission}",
            )
        return membership

    return checker
