"""Hashes scrypt y tokens HMAC compatibles con cuentas y sesiones anteriores."""

import base64
import hashlib
import hmac
import json
import math
import secrets
import time

MAX_AGE = 60 * 60 * 24 * 7


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt if salt is not None else secrets.token_hex(16)
    # Node usa el texto hexadecimal como salt, no sus bytes decodificados.
    hashed = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=64)
    return f"{salt}:{hashed.hex()}"


def password_matches(password: str, stored: str) -> bool:
    try:
        salt, saved = stored.split(":")
        if len(salt) != 32 or len(saved) != 128:
            return False
        candidate = hash_password(password, salt).split(":")[1]
        return hmac.compare_digest(saved, candidate)
    except (ValueError, TypeError, AttributeError):
        return False


def _sign(payload: str, secret: str) -> str:
    return _encode(hmac.digest(secret.encode(), payload.encode("ascii"), "sha256"))


def create_token(user_id: str, secret: str) -> str:
    payload = _encode(json.dumps({"sub": user_id, "exp": int(time.time()) + MAX_AGE}, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload, secret)}"


def read_token(token: str, secret: str) -> str | None:
    try:
        payload, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(payload, secret)):
            return None
        content = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        expiry = content.get("exp")
        user_id = content.get("sub")
        if (type(expiry) not in (int, float) or not math.isfinite(expiry)
                or expiry <= time.time() or not isinstance(user_id, str) or not user_id):
            return None
        return user_id
    except (ValueError, TypeError, UnicodeError, AttributeError):
        return None
