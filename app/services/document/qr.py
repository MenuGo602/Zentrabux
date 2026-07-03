"""
QR Service — hujjatlar uchun QR kod generatsiyasi.

DIQQAT: Bu yerda O'zbekistonning HUMO/UZCARD yoki Click/Payme kabi
to'lov tizimlarining rasmiy QR-to'lov standarti AMALGA OSHIRILMAGAN —
bunday integratsiya har bir to'lov provayderining o'ziga xos
spetsifikatsiyasini talab qiladi (ular bilan shartnoma/API kalitlari kerak).

Hozirgi QR faqat TEKSHIRISH/IDENTIFIKATSIYA maqsadida — u hujjat raqami,
summasi va kompaniya INN'ini oddiy matn sifatida kodlaydi, shu orqali
mijoz QR'ni skanerlab hujjat ma'lumotlarini tezda ko'ra oladi.
"""

from __future__ import annotations

import io
from decimal import Decimal

import qrcode


def generate_qr_png(data: str, box_size: int = 8, border: int = 2) -> bytes:
    """Berilgan matnni QR kod (PNG bayt) sifatida qaytaradi."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_document_verification_qr(
    document_number: str,
    company_inn: str | None,
    amount: Decimal | None = None,
) -> bytes:
    """
    Hujjat tekshiruvi uchun QR — INN, hujjat raqami va (bo'lsa) summani
    o'z ichiga oladi. Bu rasmiy bank to'lov QR'i EMAS.
    """
    parts = [f"DOC:{document_number}"]
    if company_inn:
        parts.append(f"INN:{company_inn}")
    if amount is not None:
        parts.append(f"AMT:{amount.quantize(Decimal('1'))}")

    return generate_qr_png(" | ".join(parts))
