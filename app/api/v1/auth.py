from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.telegram_auth import InitDataError, validate_login_widget_data
from app.events.bus import Event, EventType, event_bus
from app.models.all_models import User

router = APIRouter(prefix="/auth")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ─── Schemas ─────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    full_name: str
    phone: str | None = None
    email: EmailStr | None = None
    password: str
    telegram_id: int | None = None
    language: str = "uz"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    full_name: str
    phone: str | None
    email: str | None
    language: str


class TelegramAuthRequest(BaseModel):
    """Telegram Bot orqali kirish — parolsiz, telegram_id asosida.

    Foydalanuvchi birinchi marta /start bosganda avtomatik ro'yxatdan
    o'tkaziladi (agar shu telegram_id bilan hisob mavjud bo'lmasa),
    keyingi safar esa oddiy login sifatida ishlaydi.
    """

    telegram_id: int
    full_name: str
    language: str = "uz"


class RefreshRequest(BaseModel):
    refresh_token: str


class TelegramWidgetAuthRequest(BaseModel):
    """
    Telegram Login Widget qaytargan xom ma'lumot — field nomlari
    Telegram tomonidan belgilangan, o'zgartirib bo'lmaydi.
    https://core.telegram.org/widgets/login
    """

    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


# ─── Dependency ──────────────────────────────────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token noto'g'ri yoki muddati o'tgan",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Foydalanuvchi topilmadi",
        )
    return user


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Mavjudligini tekshirish
    if body.email:
        existing = await db.execute(select(User).where(User.email == body.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Bu email band")

    user = User(
        full_name=body.full_name,
        phone=body.phone,
        email=body.email,
        telegram_id=body.telegram_id,
        language=body.language,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    # Event
    await event_bus.emit(Event(
        type=EventType.USER_REGISTERED,
        company_id=None,
        user_id=user.id,
        data={"full_name": user.full_name},
    ))

    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # Email yoki phone orqali qidirish
    result = await db.execute(
        select(User).where(
            (User.email == form.username) | (User.phone == form.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login yoki parol noto'g'ri",
        )

    user.last_login = datetime.now(UTC)

    await event_bus.emit(Event(
        type=EventType.USER_LOGGED_IN,
        company_id=None,
        user_id=user.id,
        data={},
    ))

    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


async def _get_or_create_telegram_user(
    db: AsyncSession, telegram_id: int, full_name: str, language: str, source: str
) -> User:
    """/auth/telegram (bot) va /auth/telegram-widget (veb) ikkalasi ham shu logikani ishlatadi."""
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            full_name=full_name,
            telegram_id=telegram_id,
            language=language,
            password_hash=None,  # Telegram orqali kirganlar parolsiz
        )
        db.add(user)
        await db.flush()

        await event_bus.emit(Event(
            type=EventType.USER_REGISTERED,
            company_id=None,
            user_id=user.id,
            data={"full_name": user.full_name, "source": source},
        ))
    elif not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hisob faol emas")
    else:
        user.last_login = datetime.now(UTC)
        await event_bus.emit(Event(
            type=EventType.USER_LOGGED_IN,
            company_id=None,
            user_id=user.id,
            data={"source": source},
        ))

    return user


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(body: TelegramAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Telegram Bot uchun yagona kirish nuqtasi.

    Shu telegram_id bilan foydalanuvchi mavjud bo'lsa — token qaytaradi
    (login). Mavjud bo'lmasa — parolsiz yangi hisob yaratadi (register).
    Bot har safar /start'da shu endpointni chaqiraveradi, farqi yo'q.
    """
    user = await _get_or_create_telegram_user(
        db, body.telegram_id, body.full_name, body.language, source="telegram_bot"
    )

    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/telegram-widget", response_model=TokenResponse)
async def telegram_widget_auth(body: TelegramWidgetAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Veb-dashboard uchun "Login with Telegram" widget orqali kirish.

    Frontend Telegram'ning rasmiy widgetidan olgan ma'lumotni (id, first_name,
    ..., hash) shu yerga xomligicha yuboradi — biz uni bot tokeni bilan HMAC
    orqali tekshiramiz (Login Widget'ning O'ZIGA XOS algoritmi, WebApp
    initData'nikidan farqli — pastdagi validate_login_widget_data'ga qarang).
    """
    if not settings.BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Server tomonda BOT_TOKEN sozlanmagan")

    try:
        verified = validate_login_widget_data(body.model_dump(exclude_none=True), settings.BOT_TOKEN)
    except InitDataError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from None

    full_name = verified.get("first_name", "")
    if verified.get("last_name"):
        full_name = f"{full_name} {verified['last_name']}"

    user = await _get_or_create_telegram_user(
        db, int(verified["id"]), full_name.strip() or "Zentra foydalanuvchisi",
        language="uz", source="telegram_widget",
    )

    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh token asosida yangi access/refresh juftligini beradi (rotatsiya)."""
    try:
        payload = decode_token(body.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token noto'g'ri yoki muddati o'tgan",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bu access token — refresh uchun yaroqsiz",
        )

    result = await db.execute(select(User).where(User.id == payload.get("sub")))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Foydalanuvchi topilmadi")

    token_data = {"sub": str(user.id)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        full_name=current_user.full_name,
        phone=current_user.phone,
        email=current_user.email,
        language=current_user.language,
    )
