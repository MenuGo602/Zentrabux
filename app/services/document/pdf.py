"""
PDF qurish uchun umumiy vositalar (reportlab asosida).

Nega markazlashtirilgan:
    - Barcha hujjatlar (invoice, akt, shartnoma) bir xil sarlavha/footer
      uslubiga ega bo'lishi kerak
    - Unicode shrift ro'yxatga olish (o'zbek lotin tutuq belgisi — ʻ, o', g')
      faqat bitta joyda bajarilishi kerak, aks holda har bir generator
      o'zicha xato qiladigan bo'ladi

DIQQAT (shrift haqida):
    Standart reportlab shriftlari (Helvetica) WinAnsi kodировкasida va
    o'zbekcha maxsus tutuq belgisini har doim ham to'g'ri ko'rsatavermaydi.
    Agar ``settings.PDF_FONT_PATH`` (masalan DejaVuSans.ttf) berilgan bo'lsa,
    o'sha shrift ro'yxatga olinadi va ishlatiladi. Bo'lmasa, Helvetica'ga
    tushiladi va bu haqda bir marta ogohlantirish yoziladi.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from decimal import Decimal

from loguru import logger
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas

from app.core.config import settings

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 18 * mm

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

_fonts_registered = False
_font_warning_shown = False


def _ensure_fonts_registered() -> tuple[str, str]:
    """Sozlamalarda ko'rsatilgan Unicode shriftni (bo'lsa) bir marta ro'yxatga oladi.

    Qaytaradi: (regular_font_name, bold_font_name)
    """
    global _fonts_registered, _font_warning_shown, FONT_REGULAR, FONT_BOLD

    if _fonts_registered:
        return FONT_REGULAR, FONT_BOLD

    if settings.PDF_FONT_PATH:
        try:
            pdfmetrics.registerFont(TTFont("ZentraFont", settings.PDF_FONT_PATH))
            FONT_REGULAR = "ZentraFont"
            if settings.PDF_FONT_BOLD_PATH:
                pdfmetrics.registerFont(TTFont("ZentraFont-Bold", settings.PDF_FONT_BOLD_PATH))
                FONT_BOLD = "ZentraFont-Bold"
            else:
                FONT_BOLD = "ZentraFont"
            logger.info(f"PDF shrift ro'yxatga olindi: {settings.PDF_FONT_PATH}")
        except Exception as e:  # noqa: BLE001 — shrift muammosi butun generatsiyani to'xtatmasin
            logger.warning(f"PDF shriftini yuklab bo'lmadi ({settings.PDF_FONT_PATH}): {e}")
    elif not _font_warning_shown:
        logger.warning(
            "PDF_FONT_PATH sozlanmagan — standart Helvetica ishlatiladi. "
            "O'zbekcha tutuq belgisi (o', g') to'g'ri chiqmasligi mumkin. "
            "Unicode TTF shrift (masalan DejaVuSans.ttf) qo'shish tavsiya etiladi."
        )
        _font_warning_shown = True

    _fonts_registered = True
    return FONT_REGULAR, FONT_BOLD


@dataclass
class CompanyInfo:
    name: str
    inn: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None


@dataclass
class TableColumn:
    header: str
    width: float           # mm
    align: str = "left"    # left | right | center


@dataclass
class DocumentContext:
    """Bitta PDF hujjatini qurish uchun kerakli barcha ma'lumot."""

    title: str
    document_number: str
    company: CompanyInfo
    counterparty_name: str
    counterparty_inn: str | None = None
    counterparty_address: str | None = None
    issue_date: str = ""
    body_paragraphs: list[str] = field(default_factory=list)
    table_columns: list[TableColumn] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)
    totals: list[tuple[str, str]] = field(default_factory=list)  # [("Jami:", "1 000 000 so'm")]
    footer_note: str = ""
    qr_image_bytes: bytes | None = None


_CURRENCY_LABELS = {"UZS": "so'm", "USD": "$", "EUR": "€", "RUB": "₽"}


def format_amount(amount: Decimal, currency: str = "UZS") -> str:
    """1000000, 'UZS' → '1 000 000 so'm' (mahalliy standart: bo'sh joy ajratuvchi)."""
    quantized = amount.quantize(Decimal("1"))
    text = f"{quantized:,.0f}".replace(",", " ")
    label = _CURRENCY_LABELS.get(currency, currency)
    return f"{text} {label}" if label else text


class PDFBuilder:
    """
    Sarlavha/kontent/jadval/footer bilan A4 PDF quradi.

    Ishlatish:
        builder = PDFBuilder(context)
        pdf_bytes = builder.build()
    """

    def __init__(self, context: DocumentContext) -> None:
        self._ctx = context
        self._font_regular, self._font_bold = _ensure_fonts_registered()

    def build(self) -> bytes:
        buffer = io.BytesIO()
        c = pdf_canvas.Canvas(buffer, pagesize=A4)

        y = PAGE_HEIGHT - MARGIN
        y = self._draw_header(c, y)
        y = self._draw_meta(c, y)
        y = self._draw_paragraphs(c, y)
        if self._ctx.table_columns:
            y = self._draw_table(c, y)
        if self._ctx.totals:
            y = self._draw_totals(c, y)
        if self._ctx.qr_image_bytes:
            self._draw_qr(c, y)
        self._draw_footer(c)

        c.showPage()
        c.save()
        return buffer.getvalue()

    # ─── Bo'limlar ────────────────────────────────────────────────────────────
    def _draw_header(self, c: pdf_canvas.Canvas, y: float) -> float:
        c.setFont(self._font_bold, 16)
        c.drawString(MARGIN, y, self._ctx.title)
        y -= 8 * mm

        c.setFont(self._font_regular, 9)
        company = self._ctx.company
        lines = [company.name]
        if company.inn:
            lines.append(f"INN: {company.inn}")
        if company.address:
            lines.append(company.address)
        contact_bits = [x for x in (company.phone, company.email) if x]
        if contact_bits:
            lines.append(" | ".join(contact_bits))

        for line in lines:
            c.drawString(MARGIN, y, line)
            y -= 4.5 * mm

        y -= 3 * mm
        c.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
        y -= 8 * mm
        return y

    def _draw_meta(self, c: pdf_canvas.Canvas, y: float) -> float:
        c.setFont(self._font_regular, 10)
        c.drawString(MARGIN, y, f"№ {self._ctx.document_number}")
        c.drawRightString(PAGE_WIDTH - MARGIN, y, self._ctx.issue_date)
        y -= 6 * mm

        c.drawString(MARGIN, y, f"Kontragent: {self._ctx.counterparty_name}")
        y -= 5 * mm
        if self._ctx.counterparty_inn:
            c.drawString(MARGIN, y, f"INN: {self._ctx.counterparty_inn}")
            y -= 5 * mm
        if self._ctx.counterparty_address:
            c.drawString(MARGIN, y, f"Manzil: {self._ctx.counterparty_address}")
            y -= 5 * mm

        y -= 4 * mm
        return y

    def _draw_paragraphs(self, c: pdf_canvas.Canvas, y: float) -> float:
        c.setFont(self._font_regular, 10)
        for paragraph in self._ctx.body_paragraphs:
            for line in _wrap_text(paragraph, max_chars=95):
                c.drawString(MARGIN, y, line)
                y -= 5 * mm
            y -= 2 * mm
        return y

    def _draw_table(self, c: pdf_canvas.Canvas, y: float) -> float:
        columns = self._ctx.table_columns
        row_height = 7 * mm
        header_height = 8 * mm

        x = MARGIN
        c.setFont(self._font_bold, 9)
        c.setFillColor(colors.HexColor("#F1F3F5"))
        c.rect(MARGIN, y - header_height, sum(col.width for col in columns) * mm, header_height, fill=1, stroke=0)
        c.setFillColor(colors.black)

        cursor_x = x
        for col in columns:
            self._draw_cell_text(c, col.header, cursor_x, y - header_height + 2 * mm, col.width, col.align, bold=True)
            cursor_x += col.width * mm
        y -= header_height

        c.setFont(self._font_regular, 9)
        for row in self._ctx.table_rows:
            if y < MARGIN + 30 * mm:
                c.showPage()
                y = PAGE_HEIGHT - MARGIN
                c.setFont(self._font_regular, 9)

            cursor_x = x
            for col, value in zip(columns, row, strict=False):
                self._draw_cell_text(c, value, cursor_x, y - row_height + 2 * mm, col.width, col.align)
                cursor_x += col.width * mm

            y -= row_height
            c.setStrokeColor(colors.HexColor("#DEE2E6"))
            c.line(MARGIN, y, MARGIN + sum(col.width for col in columns) * mm, y)

        return y - 5 * mm

    def _draw_cell_text(
        self, c: pdf_canvas.Canvas, text: str, x: float, y: float, width_mm: float, align: str, bold: bool = False
    ) -> None:
        font = self._font_bold if bold else self._font_regular
        c.setFont(font, 9)
        if align == "right":
            c.drawRightString(x + width_mm * mm - 2 * mm, y, text)
        elif align == "center":
            c.drawCentredString(x + width_mm * mm / 2, y, text)
        else:
            c.drawString(x + 2 * mm, y, text)

    def _draw_totals(self, c: pdf_canvas.Canvas, y: float) -> float:
        c.setFont(self._font_bold, 11)
        for label, value in self._ctx.totals:
            c.drawRightString(PAGE_WIDTH - MARGIN, y, f"{label} {value}")
            y -= 6 * mm
        return y - 4 * mm

    def _draw_qr(self, c: pdf_canvas.Canvas, y: float) -> None:
        from reportlab.lib.utils import ImageReader

        qr_size = 28 * mm
        qr_y = max(MARGIN, y - qr_size)
        image = ImageReader(io.BytesIO(self._ctx.qr_image_bytes))
        c.drawImage(image, MARGIN, qr_y, width=qr_size, height=qr_size, preserveAspectRatio=True, mask="auto")

    def _draw_footer(self, c: pdf_canvas.Canvas) -> None:
        if not self._ctx.footer_note:
            return
        c.setFont(self._font_regular, 7)
        c.setFillColor(colors.grey)
        c.drawString(MARGIN, MARGIN / 2, self._ctx.footer_note)
        c.setFillColor(colors.black)


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]
