from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.permissions import require_permission
from app.engines.report.pnl import ProfitAndLossEngine
from app.engines.report.trial_balance import TrialBalanceEngine
from app.models.all_models import Company, CompanyUser, Transaction, TransactionType, User
from app.services.document.act import ActService, ActServiceError
from app.services.document.contract import ContractParty, ContractService, ContractTerms, ContractType
from app.services.document.excel import ExcelExportService
from app.services.document.invoice import InvoiceService, InvoiceServiceError

router = APIRouter(prefix="/documents")

invoice_service = InvoiceService()
act_service = ActService()
contract_service = ContractService()
excel_service = ExcelExportService()
pnl_engine = ProfitAndLossEngine()
trial_balance_engine = TrialBalanceEngine()


# ─── Schemas ─────────────────────────────────────────────────────────────────
class ContractPartyRequest(BaseModel):
    name: str
    inn: str | None = None
    address: str | None = None
    phone: str | None = None
    representative: str | None = None


class ContractGenerateRequest(BaseModel):
    counterparty: ContractPartyRequest
    contract_type: ContractType
    subject_description: str
    amount: Decimal
    currency: str = "UZS"
    payment_terms: str | None = None
    duration_description: str | None = None
    additional_clauses: list[str] = []
    contract_number: str | None = None


# ─── Yordamchi ────────────────────────────────────────────────────────────────
def _pdf_response(pdf_bytes: bytes, filename: str) -> StreamingResponse:
    import io

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _xlsx_response(xlsx_bytes: bytes, filename: str) -> StreamingResponse:
    import io

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _get_company_or_404(company_id: UUID, db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Kompaniya topilmadi")
    return company


# ─── PDF hujjatlar ────────────────────────────────────────────────────────────
@router.get("/{company_id}/invoice/{transaction_id}")
async def generate_invoice(
    company_id: UUID,
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("document.generate")),
    db: AsyncSession = Depends(get_db),
):
    """Bitta tranzaksiya asosida hisob-faktura (invoice) PDF generatsiya qiladi."""
    try:
        pdf_bytes = await invoice_service.generate(str(company_id), str(transaction_id), db)
    except InvoiceServiceError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return _pdf_response(pdf_bytes, f"invoice-{str(transaction_id)[:8]}.pdf")


@router.get("/{company_id}/act/{transaction_id}")
async def generate_act(
    company_id: UUID,
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("document.generate")),
    db: AsyncSession = Depends(get_db),
):
    """Bajarilgan ishlar/xizmatlar dalolatnomasi (akt) PDF generatsiya qiladi."""
    try:
        pdf_bytes = await act_service.generate(str(company_id), str(transaction_id), db)
    except ActServiceError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return _pdf_response(pdf_bytes, f"akt-{str(transaction_id)[:8]}.pdf")


@router.post("/{company_id}/contract")
async def generate_contract(
    company_id: UUID,
    body: ContractGenerateRequest,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("document.generate")),
    db: AsyncSession = Depends(get_db),
):
    """Standart shartnoma shablonini PDF sifatida generatsiya qiladi (yuridik maslahat emas)."""
    company = await _get_company_or_404(company_id, db)

    contract_party = ContractParty(
        name=company.name, inn=company.inn, address=company.address, phone=company.phone,
    )
    counterparty = ContractParty(
        name=body.counterparty.name,
        inn=body.counterparty.inn,
        address=body.counterparty.address,
        phone=body.counterparty.phone,
        representative=body.counterparty.representative,
    )

    terms_kwargs = {
        "contract_type": body.contract_type,
        "subject_description": body.subject_description,
        "amount": body.amount,
        "currency": body.currency,
        "additional_clauses": body.additional_clauses,
    }
    if body.payment_terms:
        terms_kwargs["payment_terms"] = body.payment_terms
    if body.duration_description:
        terms_kwargs["duration_description"] = body.duration_description

    terms = ContractTerms(**terms_kwargs)
    contract_number = body.contract_number or f"{date.today():%Y%m%d}-{str(company_id)[:8]}"

    pdf_bytes = contract_service.generate(contract_party, counterparty, terms, contract_number)
    return _pdf_response(pdf_bytes, f"shartnoma-{contract_number}.pdf")


# ─── Excel eksportlar ──────────────────────────────────────────────────────────
@router.get("/{company_id}/export/transactions")
async def export_transactions_excel(
    company_id: UUID,
    transaction_type: TransactionType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("report.view")),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company_or_404(company_id, db)

    filters = [Transaction.company_id == company_id]
    if transaction_type:
        filters.append(Transaction.transaction_type == transaction_type)
    if date_from:
        filters.append(Transaction.transaction_date >= date_from)
    if date_to:
        filters.append(Transaction.transaction_date <= date_to)

    result = await db.execute(
        select(Transaction).where(and_(*filters)).order_by(Transaction.transaction_date.desc()).limit(5000)
    )
    transactions = list(result.scalars().all())

    xlsx_bytes = excel_service.export_transactions(transactions, company_name=company.name)
    return _xlsx_response(xlsx_bytes, f"tranzaksiyalar-{date.today()}.xlsx")


@router.get("/{company_id}/export/trial-balance")
async def export_trial_balance_excel(
    company_id: UUID,
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("report.view")),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company_or_404(company_id, db)
    trial_balance = await trial_balance_engine.generate(str(company_id), db, period_start, period_end)

    xlsx_bytes = excel_service.export_trial_balance(trial_balance, company_name=company.name)
    return _xlsx_response(xlsx_bytes, f"aylanma-qaydnoma-{date.today()}.xlsx")


@router.get("/{company_id}/export/pnl")
async def export_pnl_excel(
    company_id: UUID,
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("report.view")),
    db: AsyncSession = Depends(get_db),
):
    company = await _get_company_or_404(company_id, db)
    pnl = await pnl_engine.generate(str(company_id), db, period_start, period_end)

    xlsx_bytes = excel_service.export_pnl(pnl, company_name=company.name)
    return _xlsx_response(xlsx_bytes, f"foyda-zarar-{date.today()}.xlsx")
