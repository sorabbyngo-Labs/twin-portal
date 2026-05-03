"""
bridge/auth.py -- Portal authentication
Uses the same TwinSession concept from chameha/identity.py.
JWT tokens signed with PORTAL_SECRET, bound to owner_id.
"""
from __future__ import annotations
import hashlib, hmac, jwt, logging, os, time
from typing import Optional

log = logging.getLogger("portal.auth")

SECRET   = os.getenv("PORTAL_SECRET", "dev-secret-change-in-production")
TTL_S    = int(os.getenv("PORTAL_SESSION_TTL_S", str(8 * 3600)))
USERS_RAW = os.getenv("PORTAL_USERS", "jonah:jonah_01:changeme")
# format: "username:owner_id:password,username2:owner_id2:password2"


def _load_users() -> dict[str, dict]:
    users = {}
    for entry in USERS_RAW.split(","):
        parts = entry.strip().split(":")
        if len(parts) == 3:
            username, owner_id, password = parts
            users[username] = {
                "owner_id": owner_id,
                "password_hash": hashlib.sha256(password.encode()).hexdigest(),
            }
    return users


_USERS = _load_users()


def authenticate(username: str, password: str) -> Optional[str]:
    """
    Verify credentials and return a signed JWT token.
    Returns None if authentication fails.
    """
    user = _USERS.get(username)
    if not user:
        log.warning("auth failed: unknown user %s", username)
        return None
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if not hmac.compare_digest(pw_hash, user["password_hash"]):
        log.warning("auth failed: wrong password for %s", username)
        return None
    token = jwt.encode({
        "sub":      username,
        "owner_id": user["owner_id"],
        "iat":      int(time.time()),
        "exp":      int(time.time()) + TTL_S,
    }, SECRET, algorithm="HS256")
    log.info("auth success: %s (owner: %s)", username, user["owner_id"])
    return token


def verify_token(token: str) -> Optional[dict]:
    """
    Verify a JWT token and return the payload.
    Returns None if invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        log.debug("token expired")
        return None
    except jwt.InvalidTokenError as e:
        log.debug("invalid token: %s", e)
        return None


def get_owner_id(token: str) -> Optional[str]:
    payload = verify_token(token)
    return payload["owner_id"] if payload else None
