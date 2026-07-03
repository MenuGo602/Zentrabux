"""
Auth API testlari — ayniqsa Telegram Bot uchun qo'shilgan
/auth/telegram va /auth/refresh endpointlari.

Bu testlar FastAPI route funksiyalarini to'g'ridan-to'g'ri chaqiradi
(loyihadagi boshqa testlar bilan bir xil uslubda — HTTP TestClient
o'rniga business-logic darajasida tekshiradi).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import (
    RefreshRequest,
    TelegramAuthRequest,
    refresh_token,
    telegram_auth,
)
from app.core.security import decode_token
from app.models.all_models import User


class TestTelegramAuth:
    async def test_creates_new_user_on_first_login(self, db_session: AsyncSession):
        body = TelegramAuthRequest(telegram_id=111222333, full_name="Aziz Aliyev")

        tokens = await telegram_auth(body, db_session)

        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.token_type == "bearer"

        result = await db_session.execute(
            select(User).where(User.telegram_id == 111222333)
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.full_name == "Aziz Aliyev"
        assert user.password_hash is None  # Telegram orqali — parolsiz

    async def test_logs_in_existing_user_without_duplicating(self, db_session: AsyncSession):
        first = TelegramAuthRequest(telegram_id=444555666, full_name="Malika Yusupova")
        await telegram_auth(first, db_session)
        await db_session.flush()

        second = TelegramAuthRequest(telegram_id=444555666, full_name="Malika Yusupova")
        await telegram_auth(second, db_session)
        await db_session.flush()

        result = await db_session.execute(
            select(User).where(User.telegram_id == 444555666)
        )
        users = result.scalars().all()
        assert len(users) == 1  # Ikkinchi chaqiruv yangi hisob yaratmadi

    async def test_access_token_contains_correct_subject(self, db_session: AsyncSession):
        body = TelegramAuthRequest(telegram_id=777888999, full_name="Diyor Karimov")
        tokens = await telegram_auth(body, db_session)

        result = await db_session.execute(
            select(User).where(User.telegram_id == 777888999)
        )
        user = result.scalar_one()

        payload = decode_token(tokens.access_token)
        assert payload["sub"] == str(user.id)
        assert payload["type"] == "access"


class TestRefreshToken:
    async def test_refresh_returns_new_valid_access_token(self, db_session: AsyncSession):
        login = await telegram_auth(
            TelegramAuthRequest(telegram_id=123123123, full_name="Test User"), db_session
        )

        new_tokens = await refresh_token(RefreshRequest(refresh_token=login.refresh_token), db_session)

        payload = decode_token(new_tokens.access_token)
        assert payload["type"] == "access"

    async def test_rejects_access_token_used_as_refresh(self, db_session: AsyncSession):
        login = await telegram_auth(
            TelegramAuthRequest(telegram_id=321321321, full_name="Test User 2"), db_session
        )

        with pytest.raises(Exception):  # HTTPException 401
            await refresh_token(RefreshRequest(refresh_token=login.access_token), db_session)

    async def test_rejects_garbage_token(self, db_session: AsyncSession):
        with pytest.raises(Exception):  # HTTPException 401
            await refresh_token(RefreshRequest(refresh_token="not-a-real-token"), db_session)
