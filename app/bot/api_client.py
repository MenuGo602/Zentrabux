"""
Zentra API Client — bot uchun backend FastAPI bilan ishlaydigan HTTP klient.

Dizayn qoidasi: bot ichida hech qanday biznes-mantiq (soliq, hisob-kitob,
ruxsatlar) YO'Q — bu klient faqat HTTP so'rov yuboradi va javobni qaytaradi.
Access token muddati o'tgan bo'lsa, avtomatik ravishda refresh qilib,
so'rovni bir marta qayta uradi.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from app.bot.session_store import BotSession, session_store
from app.core.config import settings


class APIError(Exception):
    """Backend 2xx/3xx dan boshqa status qaytarganda ko'tariladi."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class AuthRequiredError(Exception):
    """Sessiya yo'q yoki refresh ham muvaffaqiyatsiz bo'lganda — foydalanuvchi qayta /start bosishi kerak."""


class ZentraAPIClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.API_BASE_URL).rstrip("/")
        self._prefix = settings.API_V1_PREFIX

    def _url(self, path: str) -> str:
        return f"{self._base_url}{self._prefix}{path}"

    # ─── Autentifikatsiya (token talab qilmaydi) ─────────────────────────────
    async def telegram_login(self, telegram_id: int, full_name: str, language: str = "uz") -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                self._url("/auth/telegram"),
                json={"telegram_id": telegram_id, "full_name": full_name, "language": language},
            )
            self._raise_for_status(resp)
            return resp.json()

    async def _refresh(self, refresh_token: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                self._url("/auth/refresh"),
                json={"refresh_token": refresh_token},
            )
            self._raise_for_status(resp)
            return resp.json()

    # ─── Umumiy so'rov (token bilan, kerak bo'lsa avtomatik refresh) ────────
    async def request(
        self,
        telegram_id: int,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        session = await session_store.get(telegram_id)
        if session is None:
            raise AuthRequiredError("Sessiya topilmadi — /start bosing")

        response = await self._do_request(session.access_token, method, path, json_body, params)

        if response.status_code == 401:
            # Access token eskirgan bo'lishi mumkin — refresh qilib qayta urinamiz
            try:
                tokens = await self._refresh(session.refresh_token)
            except APIError:
                await session_store.delete(telegram_id)
                raise AuthRequiredError("Sessiya muddati tugagan — /start bosing") from None

            session.access_token = tokens["access_token"]
            session.refresh_token = tokens["refresh_token"]
            await session_store.set(session)

            response = await self._do_request(session.access_token, method, path, json_body, params)

        self._raise_for_status(response)
        if response.status_code == 204 or not response.content:
            return None

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.content  # PDF/Excel bayt oqimi

    async def _do_request(
        self,
        access_token: str,
        method: str,
        path: str,
        json_body: dict | None,
        params: dict | None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.request(
                method,
                self._url(path),
                json=json_body,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            logger.warning(f"API xato: {response.status_code} {response.request.url} | {detail}")
            raise APIError(response.status_code, str(detail))

    # ─── Qulaylik metodlari (ko'p ishlatiladigan endpointlar) ───────────────
    async def get_me(self, telegram_id: int) -> dict:
        return await self.request(telegram_id, "GET", "/auth/me")

    async def list_companies(self, telegram_id: int) -> list[dict]:
        return await self.request(telegram_id, "GET", "/companies")

    async def create_company(self, telegram_id: int, name: str, **extra: Any) -> dict:
        return await self.request(telegram_id, "POST", "/companies", json_body={"name": name, **extra})

    async def ai_chat(
        self, telegram_id: int, company_id: str, message: str, session_id: str | None = None
    ) -> dict:
        return await self.request(
            telegram_id,
            "POST",
            f"/ai/{company_id}/chat",
            json_body={"message": message, "session_id": session_id},
        )

    async def ai_ocr(self, telegram_id: int, company_id: str, image_base64: str, media_type: str) -> dict:
        return await self.request(
            telegram_id,
            "POST",
            f"/ai/{company_id}/ocr",
            json_body={"image_base64": image_base64, "media_type": media_type},
        )

    async def list_transactions(self, telegram_id: int, company_id: str, limit: int = 10) -> list[dict]:
        return await self.request(
            telegram_id, "GET", f"/transactions/{company_id}", params={"limit": limit}
        )

    async def create_transaction(self, telegram_id: int, company_id: str, **body: Any) -> dict:
        return await self.request(telegram_id, "POST", f"/transactions/{company_id}", json_body=body)

    async def confirm_transaction(self, telegram_id: int, company_id: str, transaction_id: str) -> dict:
        return await self.request(
            telegram_id, "PATCH", f"/transactions/{company_id}/{transaction_id}/confirm"
        )

    async def dashboard(self, telegram_id: int, company_id: str, period_start: str, period_end: str) -> dict:
        return await self.request(
            telegram_id,
            "GET",
            f"/reports/{company_id}/dashboard",
            params={"period_start": period_start, "period_end": period_end},
        )

    async def list_debts(self, telegram_id: int, company_id: str, overdue_only: bool = False) -> list[dict]:
        path = f"/debts/{company_id}/overdue" if overdue_only else f"/debts/{company_id}"
        return await self.request(telegram_id, "GET", path)

    async def create_debt(self, telegram_id: int, company_id: str, **body: Any) -> dict:
        return await self.request(telegram_id, "POST", f"/debts/{company_id}", json_body=body)

    async def list_customers(self, telegram_id: int, company_id: str, search: str | None = None) -> list[dict]:
        params = {"search": search} if search else None
        return await self.request(telegram_id, "GET", f"/customers/{company_id}", params=params)

    async def create_customer(self, telegram_id: int, company_id: str, name: str, **extra: Any) -> dict:
        return await self.request(
            telegram_id, "POST", f"/customers/{company_id}", json_body={"name": name, **extra}
        )

    async def list_suppliers(self, telegram_id: int, company_id: str, search: str | None = None) -> list[dict]:
        params = {"search": search} if search else None
        return await self.request(telegram_id, "GET", f"/suppliers/{company_id}", params=params)

    async def create_supplier(self, telegram_id: int, company_id: str, name: str, **extra: Any) -> dict:
        return await self.request(
            telegram_id, "POST", f"/suppliers/{company_id}", json_body={"name": name, **extra}
        )

    async def debts_aging(self, telegram_id: int, company_id: str) -> dict:
        return await self.request(telegram_id, "GET", f"/debts/{company_id}/aging")

    async def upcoming_tax_deadlines(self, telegram_id: int, days_ahead: int = 30) -> dict:
        return await self.request(
            telegram_id, "GET", "/tax/calendar/upcoming", params={"days_ahead": days_ahead}
        )

    async def calculate_vat(self, telegram_id: int, company_id: str, amount: float) -> dict:
        return await self.request(
            telegram_id, "POST", f"/tax/{company_id}/calculate-vat", json_body={"amount": amount}
        )

    async def generate_invoice(self, telegram_id: int, company_id: str, transaction_id: str) -> bytes:
        return await self.request(telegram_id, "GET", f"/documents/{company_id}/invoice/{transaction_id}")

    async def generate_act(self, telegram_id: int, company_id: str, transaction_id: str) -> bytes:
        return await self.request(telegram_id, "GET", f"/documents/{company_id}/act/{transaction_id}")

    async def export_transactions_excel(self, telegram_id: int, company_id: str) -> bytes:
        return await self.request(telegram_id, "GET", f"/documents/{company_id}/export/transactions")


api_client = ZentraAPIClient()
