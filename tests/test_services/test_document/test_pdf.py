from decimal import Decimal

from app.services.document.pdf import (
    CompanyInfo,
    DocumentContext,
    PDFBuilder,
    TableColumn,
    format_amount,
)
from app.services.document.qr import generate_qr_png


class TestFormatAmount:
    def test_formats_uzs_with_space_separators(self):
        assert format_amount(Decimal("1000000"), "UZS") == "1 000 000 so'm"

    def test_formats_small_amount(self):
        assert format_amount(Decimal("500"), "UZS") == "500 so'm"

    def test_formats_unknown_currency_uses_code(self):
        assert format_amount(Decimal("100"), "XYZ") == "100 XYZ"

    def test_rounds_to_whole_number(self):
        assert format_amount(Decimal("1234.56"), "UZS") == "1 235 so'm"


class TestPDFBuilder:
    def test_produces_valid_pdf_bytes(self):
        context = DocumentContext(
            title="TEST HUJJAT",
            document_number="001",
            company=CompanyInfo(name="Test MCHJ", inn="123456789"),
            counterparty_name="Test Mijoz",
            issue_date="2026-07-01",
            body_paragraphs=["Bu test hujjat matni."],
        )

        pdf_bytes = PDFBuilder(context).build()

        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 500

    def test_produces_valid_pdf_with_table(self):
        context = DocumentContext(
            title="HISOB-FAKTURA",
            document_number="INV-001",
            company=CompanyInfo(name="Test MCHJ"),
            counterparty_name="Mijoz XYZ",
            issue_date="2026-07-01",
            table_columns=[
                TableColumn("№", 10, "center"),
                TableColumn("Tavsif", 100, "left"),
                TableColumn("Summa", 40, "right"),
            ],
            table_rows=[["1", "Tovar A", "100 000 so'm"], ["2", "Tovar B", "200 000 so'm"]],
            totals=[("Jami:", "300 000 so'm")],
        )

        pdf_bytes = PDFBuilder(context).build()

        assert pdf_bytes.startswith(b"%PDF")

    def test_handles_many_rows_with_page_break(self):
        rows = [[str(i), f"Mahsulot {i}", "10 000 so'm"] for i in range(60)]
        context = DocumentContext(
            title="Katta hisobot",
            document_number="002",
            company=CompanyInfo(name="Test MCHJ"),
            counterparty_name="Mijoz",
            table_columns=[
                TableColumn("№", 10, "center"),
                TableColumn("Nomi", 100, "left"),
                TableColumn("Summa", 40, "right"),
            ],
            table_rows=rows,
        )

        pdf_bytes = PDFBuilder(context).build()

        assert pdf_bytes.startswith(b"%PDF")

    def test_embeds_qr_image_without_error(self):
        qr_bytes = generate_qr_png("test-data")
        context = DocumentContext(
            title="QR bilan hujjat",
            document_number="003",
            company=CompanyInfo(name="Test MCHJ"),
            counterparty_name="Mijoz",
            qr_image_bytes=qr_bytes,
        )

        pdf_bytes = PDFBuilder(context).build()

        assert pdf_bytes.startswith(b"%PDF")
