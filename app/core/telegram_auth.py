"""
Telegram Mini App uchun initData validatsiyasi.

Telegram hujjatiga ko'ra (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app):
    secret_key = HMAC_SHA256(bot_token, key="WebAppData")
    data_check_string = "hash" dan boshqa barcha key=value juftliklari,
                         kalit bo'yicha alifbo tartibida saralangan, "\n" bilan qo'shilgan
    hash == HMAC_SHA256(data_check_string, key=secret_key).hexdigest()

Bu HMAC imzosi Telegram'ning o'zi tomonidan Mini App ochilganda yaratiladi —
shuning uchun uni tekshirish "bu so'rov haqiqatan ham Telegramdan va aynan
shu foydalanuvchidan kelyaptimi" degan savolga xavfsiz javob beradi.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    """initData yaroqsiz, imzo mos kelmadi yoki muddati o'tgan."""


def validate_login_widget_data(auth_data: dict, bot_token: str, max_age_seconds: int = 86400) -> dict:
    """
    Telegram Login Widget orqali kelgan ma'lumotni tekshiradi.

    MUHIM: bu WebApp initData'dan BOSHQA algoritm ishlatadi —
    https://core.telegram.org/widgets/login#checking-authorization
        secret_key = SHA256(bot_token)               (WebApp'da: HMAC-SHA256 "WebAppData" kaliti bilan)
        hash = HMAC_SHA256(data_check_string, secret_key).hexdigest()

    `auth_data` — widgetdan JSON sifatida kelgan lug'at:
        {id, first_name, last_name?, username?, photo_url?, auth_date, hash}
    """
    data = dict(auth_data)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise InitDataError("Ma'lumotda 'hash' yo'q")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()) if v is not None)

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InitDataError("Imzo mos kelmadi — ma'lumot soxta bo'lishi mumkin")

    auth_date = data.get("auth_date")
    if auth_date and (time.time() - int(auth_date)) > max_age_seconds:
        raise InitDataError("Kirish havolasi muddati o'tgan — qaytadan urinib ko'ring")

    if "id" not in data:
        raise InitDataError("Ma'lumotda 'id' yo'q")

    return data


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict:
    """
    initData qatorini tekshiradi va undagi foydalanuvchi ma'lumotini qaytaradi.

    Qaytadi: {"id": int, "first_name": str, "last_name": str|None,
              "username": str|None, "language_code": str|None}

    Xato bo'lsa: InitDataError ko'taradi.
    """
    if not init_data:
        raise InitDataError("initData bo'sh")

    pairs = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("initData'da 'hash' yo'q")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InitDataError("Imzo mos kelmadi — initData soxta bo'lishi mumkin")

    auth_date = pairs.get("auth_date")
    if auth_date and (time.time() - int(auth_date)) > max_age_seconds:
        raise InitDataError("initData muddati o'tgan — Mini App'ni qayta oching")

    user_raw = pairs.get("user")
    if not user_raw:
        raise InitDataError("initData'da 'user' maydoni yo'q")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as e:
        raise InitDataError("'user' maydoni JSON emas") from e

    if "id" not in user:
        raise InitDataError("'user' ichida 'id' yo'q")

    return user
