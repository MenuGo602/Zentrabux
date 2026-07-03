from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.engines.report.balance_sheet import BalanceSheetEngine
from app.engines.report.cashflow import CashFlowEngine
from app.engines.report.pnl import ProfitAndLossEngine
from app.engines.report.trial_balance import TrialBalanceEngine
from app.models.all_models import User

router = APIRouter(prefix="/reports")

trial_balance_engine = TrialBalanceEngine()
pnl_engine = ProfitAndLossEngine()
balance_sheet_engine = BalanceSheetEngine()
cashflow_engine = CashFlowEngine()


@router.get("/{company_id}/trial-balance")
async def get_trial_balance(
    company_id: UUID,
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aylanma qaydnoma — barcha schyotlar bo'yicha Debit/Credit"""
    tb = await trial_balance_engine.generate(str(company_id), db, period_start, period_end)
    return {
        "period_start": str(period_start) if period_start else None,
        "period_end": str(period_end) if period_end else None,
        "lines": [
            {
                "code": l.account_code,
                "name": l.account_name,
                "type": l.account_type,
                "debit": float(l.total_debit),
                "credit": float(l.total_credit),
                "balance": float(l.balance),
            }
            for l in tb.lines
        ],
        "total_debit": float(tb.total_debit),
        "total_credit": float(tb.total_credit),
        "is_balanced": tb.is_balanced,
    }


@router.get("/{company_id}/profit-loss")
async def get_profit_loss(
    company_id: UUID,
    period_start: date = Query(...),
    period_end: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Foyda va zarar hisoboti (P&L)"""
    pnl = await pnl_engine.generate(str(company_id), db, period_start, period_end)
    return pnl.to_dict()


@router.get("/{company_id}/balance-sheet")
async def get_balance_sheet(
    company_id: UUID,
    as_of_date: date = Query(default_factory=date.today),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Buxgalteriya balansi — muayyan sananing holati"""
    sheet = await balance_sheet_engine.generate(str(company_id), db, as_of_date)
    return sheet.to_dict()


@router.get("/{company_id}/cashflow")
async def get_cashflow(
    company_id: UUID,
    period_start: date = Query(...),
    period_end: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pul oqimi hisoboti"""
    cf = await cashflow_engine.generate(str(company_id), db, period_start, period_end)
    return cf.to_dict()


@router.get("/{company_id}/dashboard")
async def get_dashboard_summary(
    company_id: UUID,
    period_start: date = Query(...),
    period_end: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bitta so'rovda barcha asosiy ko'rsatkichlar — dashboard uchun"""
    pnl = await pnl_engine.generate(str(company_id), db, period_start, period_end)
    sheet = await balance_sheet_engine.generate(str(company_id), db, period_end)
    cf = await cashflow_engine.generate(str(company_id), db, period_start, period_end)

    return {
        "period": {"start": str(period_start), "end": str(period_end)},
        "income": float(pnl.total_income),
        "expense": float(pnl.total_expense),
        "net_profit": float(pnl.net_profit),
        "profit_margin_percent": float(round(pnl.profit_margin, 2)),
        "total_assets": float(sheet.total_assets),
        "total_liabilities": float(sheet.total_liabilities),
        "cash_closing_balance": float(cf.closing_balance),
        "is_balance_sheet_balanced": sheet.is_balanced,
    }
