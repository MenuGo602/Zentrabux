from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.engines.report.pnl import ProfitAndLossEngine
from app.engines.tax.uzbekistan import UzbekistanTaxEngine
from app.models.all_models import User

router = APIRouter(prefix="/tax")

tax_engine = UzbekistanTaxEngine()
pnl_engine = ProfitAndLossEngine()


class VATCalculationRequest(BaseModel):
    amount: Decimal
    is_vat_payer: bool = True
    is_simplified: bool = False


@router.post("/{company_id}/calculate-vat")
async def calculate_vat(
    company_id: UUID,
    body: VATCalculationRequest,
    current_user: User = Depends(get_current_user),
):
    """Bitta operatsiya uchun QQS hisoblash (kalkulyator)"""
    result = await tax_engine.calculate_vat(
        taxable_amount=body.amount,
        company_id=str(company_id),
        is_vat_payer=body.is_vat_payer,
        is_simplified=body.is_simplified,
    )
    return result.to_dict() if result else {"message": "QQS to'lovchisi emas"}


@router.get("/{company_id}/period-summary")
async def get_period_tax_summary(
    company_id: UUID,
    period_start: date = Query(...),
    period_end: date = Query(...),
    is_vat_payer: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Davr uchun barcha soliqlarni hisoblaydi: QQS, foyda solig'i.
    P&L hisobotidan real foyda/aylanma olib, ustiga soliq hisoblanadi.
    """
    pnl = await pnl_engine.generate(str(company_id), db, period_start, period_end)

    vat_result = await tax_engine.calculate_vat(
        taxable_amount=pnl.total_income,
        company_id=str(company_id),
        is_vat_payer=is_vat_payer,
    )
    profit_tax_result = await tax_engine.calculate_profit_tax(
        net_profit=pnl.net_profit,
        company_id=str(company_id),
    )

    return {
        "period": {"start": str(period_start), "end": str(period_end)},
        "revenue": float(pnl.total_income),
        "net_profit": float(pnl.net_profit),
        "vat": vat_result.to_dict() if vat_result else None,
        "profit_tax": profit_tax_result.to_dict() if profit_tax_result else None,
        "total_tax_liability": float(
            (vat_result.tax_amount if vat_result else Decimal("0"))
            + (profit_tax_result.tax_amount if profit_tax_result else Decimal("0"))
        ),
    }


@router.get("/{company_id}/regime-check")
async def check_tax_regime(
    company_id: UUID,
    annual_revenue: Decimal = Query(..., description="Yillik aylanma (so'mda)"),
    current_user: User = Depends(get_current_user),
):
    """Yillik aylanmaga ko'ra qaysi soliq rejimi tegishli ekanini aniqlaydi"""
    regime = tax_engine.determine_regime(annual_revenue)
    warning = tax_engine.check_regime_transition_warning(annual_revenue)

    return {
        "annual_revenue": float(annual_revenue),
        "recommended_regime": regime,
        "regime_name": "Aylanma solig'i (soddalashtirilgan)" if regime == "turnover_tax" else "Umumiy rejim (QQS + Foyda solig'i)",
        "warning": warning,
    }


@router.get("/calendar")
async def get_tax_calendar(
    year: int = Query(default_factory=lambda: date.today().year),
    current_user: User = Depends(get_current_user),
):
    """Yillik soliq taqvimi — barcha deklaratsiya/to'lov muddatlari"""
    entries = tax_engine.get_tax_calendar(year)
    return {
        "year": year,
        "entries": [
            {
                "tax_type": e.tax_type,
                "tax_name": e.tax_name,
                "deadline": str(e.deadline),
                "period": e.period_description,
                "is_filing": e.is_filing,
            }
            for e in entries
        ],
    }


@router.get("/calendar/upcoming")
async def get_upcoming_deadlines(
    days_ahead: int = Query(30, le=90),
    current_user: User = Depends(get_current_user),
):
    """Yaqin orada keladigan soliq muddatlari (bildirishnoma uchun)"""
    upcoming = tax_engine.get_upcoming_deadlines(date.today(), days_ahead)
    return {
        "days_ahead": days_ahead,
        "deadlines": [
            {
                "tax_name": e.tax_name,
                "deadline": str(e.deadline),
                "period": e.period_description,
                "days_remaining": (e.deadline - date.today()).days,
            }
            for e in upcoming
        ],
    }
