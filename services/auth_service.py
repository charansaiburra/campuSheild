import os
import time
import hashlib
import hmac
import json
import base64
import secrets
from typing import Dict, Any, Optional

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be configured in the environment before starting the backend")
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must contain at least 32 characters")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 3600 * 24  # 24 hours
PASSWORD_HASH_ITERATIONS = 310_000
LEGACY_PASSWORD_SALT = "campushield_salt_2026"

def hash_password(password: str) -> str:
    """Hash a password using salted PBKDF2-SHA256."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PASSWORD_HASH_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify current PBKDF2 hashes or legacy hashes pending upgrade on login."""
    if hashed_password.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, digest = hashed_password.split("$", 3)
            actual = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), bytes.fromhex(salt), int(iterations)).hex()
            return hmac.compare_digest(actual, digest)
        except (ValueError, TypeError):
            return False
    legacy = hashlib.sha256((LEGACY_PASSWORD_SALT + plain_password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, hashed_password)

def is_legacy_password_hash(hashed_password: str) -> bool:
    return not hashed_password.startswith("pbkdf2_sha256$")

def create_jwt_token(payload: Dict[str, Any]) -> str:
    """Creates a simple URL-safe base64 encoded JWT token with HMAC-SHA256 signature."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    token_payload = payload.copy()
    token_payload["iat"] = now
    token_payload["exp"] = now + ACCESS_TOKEN_EXPIRE_SECONDS

    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(token_payload).encode()).decode().rstrip("=")

    signature_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(JWT_SECRET.encode(), signature_input, hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates JWT token signature and expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        signature_input = f"{header_b64}.{payload_b64}".encode()
        expected_signature = hmac.new(JWT_SECRET.encode(), signature_input, hashlib.sha256).digest()

        # Add padding back for b64decode
        rem = len(signature_b64) % 4
        if rem:
            signature_b64 += "=" * (4 - rem)
        actual_signature = base64.urlsafe_b64decode(signature_b64.encode())

        if not hmac.compare_digest(expected_signature, actual_signature):
            return None

        # Decode payload
        rem_p = len(payload_b64) % 4
        if rem_p:
            payload_b64 += "=" * (4 - rem_p)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())

        if payload.get("exp", 0) <= int(time.time()):
            return None  # Expired

        return payload
    except Exception as e:
        print(f"[AuthService] Token decode error: {e}")
        return None
