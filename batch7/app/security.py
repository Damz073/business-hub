import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.settings import get_jwt_algorithm, get_jwt_expire_minutes, get_jwt_secret_key


def gerar_senha_temporaria(tamanho: int = 10) -> str:
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256$120000${_b64e(salt)}${_b64e(dk)}"



def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, hash_b64 = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _b64d(salt_b64)
        expected = _b64d(hash_b64)
        current = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(current, expected)
    except Exception:
        return False



def create_access_token(user: dict) -> str:
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=get_jwt_expire_minutes())
    payload = {
        "sub": str(user["id"]),
        "restaurant_id": user["restaurant_id"],
        "role": user["role"],
        "type": "access",
        "exp": expire_at,
    }
    return jwt.encode(payload, get_jwt_secret_key(), algorithm=get_jwt_algorithm())



def decode_access_token(token: str) -> dict:
    return jwt.decode(token, get_jwt_secret_key(), algorithms=[get_jwt_algorithm()])
