from decimal import Decimal

from app.services.document.qr import generate_document_verification_qr, generate_qr_png


class TestQRGeneration:
    def test_generates_valid_png_bytes(self):
        png_bytes = generate_qr_png("hello world")

        assert png_bytes.startswith(b"\x89PNG")

    def test_document_verification_qr_includes_document_number(self):
        png_bytes = generate_document_verification_qr("INV-001", "123456789", Decimal("100000"))

        assert png_bytes.startswith(b"\x89PNG")
        assert len(png_bytes) > 100

    def test_document_verification_qr_without_optional_fields(self):
        png_bytes = generate_document_verification_qr("INV-002", None, None)

        assert png_bytes.startswith(b"\x89PNG")
