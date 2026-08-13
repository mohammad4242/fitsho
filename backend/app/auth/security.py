import hashlib
import hmac
import re
import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = _password_hash.hash("fitsho-dummy-password-value")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def make_session_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_session_token(raw_token)


def normalize_iranian_phone(raw_phone: str) -> str:
    phone = raw_phone.strip()
    if phone.startswith("0098"):
        phone = f"+98{phone[4:]}"
    elif phone.startswith("09"):
        phone = f"+98{phone[1:]}"
    if re.fullmatch(r"\+989\d{9}", phone) is None:
        raise ValueError("Invalid Iranian mobile number")
    return phone


def hash_password_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def make_password_reset_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_password_reset_token(raw_token)


def make_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp_code(phone_number: str, code: str, secret: str) -> str:
    payload = f"{phone_number}:{code}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
