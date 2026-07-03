"""
Telegram autentifikatsiya validatsiyasi testlari.

Bu modul faqat stdlib (hashlib/hmac/json) ishlatadi — DB yoki tashqi
kutubxonalar shart emas, shuning uchun testlar ham shunday yozilgan.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.core.telegram_auth import (
    InitDataError,
    validate_init_data,
    validate_login_widget_data,
)

BOT_TOKEN = "123456:TEST_TOKEN"


def _sign_webapp_init_data(pairs: dict) -> str:
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**pairs, "hash": signature})


def _sign_widget_data(data: dict) -> dict:
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    signature = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return {**data, "hash": signature}


class TestWebAppInitData:
    def test_accepts_correctly_signed_data(self):
        user = {"id": 555111222, "first_name": "Aziz"}
        pairs = {"user": json.dumps(user, separators=(",", ":")), "auth_date": str(int(time.time()))}

        result = validate_init_data(_sign_webapp_init_data(pairs), BOT_TOKEN)

        assert result["id"] == 555111222
        assert result["first_name"] == "Aziz"

    def test_rejects_tampered_user(self):
        user = {"id": 1, "first_name": "Aziz"}
        pairs = {"user": json.dumps(user, separators=(",", ":")), "auth_date": str(int(time.time()))}
        init_data = _sign_webapp_init_data(pairs)

        tampered = init_data.replace("Aziz", "Hacker")

        with pytest.raises(InitDataError):
            validate_init_data(tampered, BOT_TOKEN)

    def test_rejects_wrong_bot_token(self):
        user = {"id": 1, "first_name": "Aziz"}
        pairs = {"user": json.dumps(user, separators=(",", ":")), "auth_date": str(int(time.time()))}
        init_data = _sign_webapp_init_data(pairs)

        with pytest.raises(InitDataError):
            validate_init_data(init_data, "different:token")

    def test_rejects_expired_data(self):
        user = {"id": 1, "first_name": "Aziz"}
        old_auth_date = str(int(time.time()) - 2 * 86400)
        pairs = {"user": json.dumps(user, separators=(",", ":")), "auth_date": old_auth_date}

        with pytest.raises(InitDataError):
            validate_init_data(_sign_webapp_init_data(pairs), BOT_TOKEN, max_age_seconds=86400)

    def test_rejects_missing_hash(self):
        with pytest.raises(InitDataError):
            validate_init_data(urlencode({"user": "{}"}), BOT_TOKEN)

    def test_rejects_empty_string(self):
        with pytest.raises(InitDataError):
            validate_init_data("", BOT_TOKEN)


class TestLoginWidgetData:
    def test_accepts_correctly_signed_data(self):
        data = {"id": 777888999, "first_name": "Malika", "auth_date": int(time.time())}

        result = validate_login_widget_data(_sign_widget_data(data), BOT_TOKEN)

        assert result["id"] == 777888999

    def test_rejects_tampered_id(self):
        data = {"id": 1, "first_name": "Malika", "auth_date": int(time.time())}
        signed = _sign_widget_data(data)
        signed["id"] = 999999

        with pytest.raises(InitDataError):
            validate_login_widget_data(signed, BOT_TOKEN)

    def test_webapp_signature_is_not_valid_for_widget(self):
        """Ikki algoritm chalkashib ketmasligi — bu xavfsizlik uchun kritik."""
        data = {"id": 1, "first_name": "Malika", "auth_date": int(time.time())}
        check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        wrong_secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        wrong_hash = hmac.new(wrong_secret, check_string.encode(), hashlib.sha256).hexdigest()

        with pytest.raises(InitDataError):
            validate_login_widget_data({**data, "hash": wrong_hash}, BOT_TOKEN)

    def test_rejects_missing_hash(self):
        with pytest.raises(InitDataError):
            validate_login_widget_data({"id": 1, "first_name": "Malika"}, BOT_TOKEN)
