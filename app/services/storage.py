"""
Storage Service — generatsiya qilingan fayllarni (invoice PDF, Excel export
va h.k.) saqlash uchun backend-agnostik qatlam.

``STORAGE_BACKEND`` sozlamasiga qarab ishlaydi:
    - "local": diskka yozadi (``STORAGE_LOCAL_PATH``)
    - "s3" / "minio": boto3 orqali S3-mos xotiraga yozadi
      (MinIO uchun ``AWS_S3_ENDPOINT_URL`` beriladi)

Hujjat generatorlar (invoice/act/contract/excel) bu servisdan foydalanib
o'zlari qayerga yozishni bilishlari shart emas.
"""

from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from loguru import logger

from app.core.config import settings


class StorageError(Exception):
    """Faylni saqlash/o'qishda xato yuz berganda ko'tariladi."""


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, key: str, data: bytes, content_type: str) -> str:
        """Faylni saqlaydi va uni topish uchun manzil/URL qaytaradi."""
        ...

    @abstractmethod
    async def load(self, key: str) -> bytes:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Path traversal'dan himoya — kalitni faqat fayl nomi sifatida ishlatamiz
        safe_key = key.replace("..", "").lstrip("/")
        path = (self._base_path / safe_key).resolve()
        if not str(path).startswith(str(self._base_path.resolve())):
            raise StorageError(f"Noto'g'ri fayl kaliti: {key}")
        return path

    async def save(self, key: str, data: bytes, content_type: str) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    async def load(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise StorageError(f"Fayl topilmadi: {key}")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            os.remove(path)


class S3StorageBackend(StorageBackend):
    """AWS S3 va MinIO uchun (ikkalasi ham S3-mos API ishlatadi)."""

    def __init__(
        self,
        bucket: str,
        region: str,
        access_key: str,
        secret_key: str,
        endpoint_url: str = "",
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._access_key = access_key
        self._secret_key = secret_key
        self._endpoint_url = endpoint_url or None

    def _client(self):
        import boto3

        return boto3.client(
            "s3",
            region_name=self._region,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            endpoint_url=self._endpoint_url,
        )

    async def save(self, key: str, data: bytes, content_type: str) -> str:
        import asyncio

        def _put() -> None:
            self._client().put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
            )

        try:
            await asyncio.to_thread(_put)
        except Exception as e:  # noqa: BLE001 — boto3 xatolarini birxillashtiramiz
            logger.error(f"S3 saqlash xato: {e}")
            raise StorageError(str(e)) from e

        if self._endpoint_url:
            return f"{self._endpoint_url.rstrip('/')}/{self._bucket}/{key}"
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"

    async def load(self, key: str) -> bytes:
        import asyncio

        def _get() -> bytes:
            response = self._client().get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()

        try:
            return await asyncio.to_thread(_get)
        except Exception as e:  # noqa: BLE001
            logger.error(f"S3 o'qish xato: {e}")
            raise StorageError(str(e)) from e

    async def delete(self, key: str) -> None:
        import asyncio

        def _delete() -> None:
            self._client().delete_object(Bucket=self._bucket, Key=key)

        try:
            await asyncio.to_thread(_delete)
        except Exception as e:  # noqa: BLE001
            logger.error(f"S3 o'chirish xato: {e}")
            raise StorageError(str(e)) from e


class StorageService:
    """Yuqori darajadagi kirish nuqtasi — sozlamalarga qarab backend tanlaydi."""

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self._backend = backend or self._build_default_backend()

    @staticmethod
    def _build_default_backend() -> StorageBackend:
        if settings.STORAGE_BACKEND == "local":
            return LocalStorageBackend(settings.STORAGE_LOCAL_PATH)
        return S3StorageBackend(
            bucket=settings.AWS_BUCKET_NAME,
            region=settings.AWS_REGION,
            access_key=settings.AWS_ACCESS_KEY_ID,
            secret_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.MINIO_URL,
        )

    @staticmethod
    def build_key(*, company_id: str, category: str, extension: str) -> str:
        """Kolliziyasiz, tartiblangan fayl kaliti yaratadi.

        Masalan: ``documents/{company_id}/invoices/{uuid}.pdf``
        """
        return f"documents/{company_id}/{category}/{uuid.uuid4()}.{extension}"

    async def save(self, key: str, data: bytes, content_type: str) -> str:
        return await self._backend.save(key, data, content_type)

    async def load(self, key: str) -> bytes:
        return await self._backend.load(key)

    async def delete(self, key: str) -> None:
        await self._backend.delete(key)
