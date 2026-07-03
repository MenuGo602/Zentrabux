import tempfile

import pytest

from app.services.storage import LocalStorageBackend, StorageError, StorageService


class TestLocalStorageBackend:
    async def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            backend = LocalStorageBackend(tmp_dir)

            await backend.save("test/file.txt", b"hello world", "text/plain")
            loaded = await backend.load("test/file.txt")

            assert loaded == b"hello world"

    async def test_load_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            backend = LocalStorageBackend(tmp_dir)

            with pytest.raises(StorageError):
                await backend.load("nonexistent.txt")

    async def test_delete_removes_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            backend = LocalStorageBackend(tmp_dir)
            await backend.save("to_delete.txt", b"data", "text/plain")

            await backend.delete("to_delete.txt")

            with pytest.raises(StorageError):
                await backend.load("to_delete.txt")

    async def test_sanitizes_path_traversal_attempts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            backend = LocalStorageBackend(tmp_dir)

            saved_path = await backend.save("../../etc/passwd", b"malicious", "text/plain")

            # Fayl asosiy katalog ichida qolishi kerak, undan tashqariga chiqmasligi kerak
            assert saved_path.startswith(tmp_dir) or tmp_dir in saved_path


class TestStorageServiceKeyBuilder:
    def test_build_key_produces_unique_keys(self):
        key1 = StorageService.build_key(company_id="abc", category="invoices", extension="pdf")
        key2 = StorageService.build_key(company_id="abc", category="invoices", extension="pdf")

        assert key1 != key2
        assert key1.startswith("documents/abc/invoices/")
        assert key1.endswith(".pdf")
