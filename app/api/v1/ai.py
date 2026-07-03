from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.all_models import AIConversation, CompanyUser, User
from app.services.ai.memory import AIMemoryService
from app.services.ai.ocr import OCRService
from app.services.ai.orchestrator import AIOrchestrator
from app.services.ai.schemas import AIResponse, OCRResult

router = APIRouter(prefix="/ai")

orchestrator = AIOrchestrator()
ocr_service = OCRService()
memory_service = AIMemoryService()


# ─── Schemas ─────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class OCRRequest(BaseModel):
    image_base64: str
    media_type: str = "image/jpeg"


class ConversationMessage(BaseModel):
    id: UUID
    message_role: str
    content: str
    intent: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.post("/{company_id}/chat", response_model=AIResponse)
async def chat(
    company_id: UUID,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("ai.chat")),
    db: AsyncSession = Depends(get_db),
):
    """
    Asosiy AI suhbat kirish nuqtasi (Telegram bot, Web Dashboard,
    Mobile App — barchasi shu endpointdan foydalanadi).

    AI faqat niyatni aniqlaydi va ma'lumotlarni ajratadi — yakuniy
    hisob-kitob va yozuvlar har doim Accounting/Tax Engine orqali bajariladi.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Xabar bo'sh bo'lishi mumkin emas")

    return await orchestrator.process_message(
        company_id=str(company_id),
        user_id=str(current_user.id),
        message=body.message,
        db=db,
        session_id=body.session_id,
    )


@router.post("/{company_id}/ocr", response_model=OCRResult)
async def extract_receipt(
    company_id: UUID,
    body: OCRRequest,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("ai.chat")),
):
    """
    Chek/faktura rasmidan ma'lumot o'qiydi.

    Bu endpoint faqat ma'lumotni QAYTARADI — tranzaksiya yaratmaydi.
    Foydalanuvchi natijani ko'rib, tasdiqlasa, alohida
    POST /transactions/{company_id} chaqiriladi (yoki AI chat orqali
    "tasdiqlayman" deyiladi).
    """
    try:
        return await ocr_service.extract_from_image(body.image_base64, body.media_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{company_id}/conversations", response_model=list[ConversationMessage])
async def get_conversation_history(
    company_id: UUID,
    session_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("ai.chat")),
    db: AsyncSession = Depends(get_db),
):
    """AI suhbat tarixi — bitta sessiya yoki foydalanuvchining barcha xabarlari."""
    filters = [
        AIConversation.company_id == company_id,
        AIConversation.user_id == current_user.id,
    ]
    if session_id:
        filters.append(AIConversation.session_id == session_id)

    result = await db.execute(
        select(AIConversation)
        .where(*filters)
        .order_by(AIConversation.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()  # eskidan yangiga
    return messages


@router.get("/{company_id}/memory")
async def list_ai_memory(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("ai.chat")),
    db: AsyncSession = Depends(get_db),
):
    """AI o'rgangan xatti-harakat naqshlari (masalan, kontragent → kategoriya)."""
    memories = await memory_service.list_memories(str(company_id), str(current_user.id), db)
    return [
        {
            "id": str(m.id),
            "memory_type": m.memory_type,
            "key": m.key,
            "value": m.value,
            "confidence": float(m.confidence),
            "occurrences": m.occurrences,
            "last_used": str(m.last_used),
        }
        for m in memories
    ]


@router.delete("/{company_id}/memory/{memory_id}")
async def forget_memory(
    company_id: UUID,
    memory_id: UUID,
    current_user: User = Depends(get_current_user),
    membership: CompanyUser = Depends(require_permission("ai.chat")),
    db: AsyncSession = Depends(get_db),
):
    """Foydalanuvchi AI noto'g'ri o'rgangan naqshni o'chirib tashlashi mumkin."""
    deleted = await memory_service.forget(str(memory_id), db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Xotira topilmadi")
    return {"status": "deleted", "id": str(memory_id)}
