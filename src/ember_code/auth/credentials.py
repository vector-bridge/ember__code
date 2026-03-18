"""Token persistence — save, load, validate, and clear stored credentials."""

import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_CREDENTIALS_PATH = "~/.ember/credentials.json"

# JWT default lifetime: 7 days
DEFAULT_TOKEN_TTL = 7 * 24 * 3600


class Credentials(BaseModel):
    """Stored authentication credentials."""

    access_token: str
    token_type: str = "bearer"
    email: str = ""
    created_at: str = ""
    expires_at: str = ""


def _credentials_path(path: str | None = None) -> Path:
    """Resolve the credentials file path."""
    return Path(os.path.expanduser(path or DEFAULT_CREDENTIALS_PATH))


def save_credentials(
    token: str,
    email: str,
    path: str | None = None,
    ttl: int = DEFAULT_TOKEN_TTL,
) -> None:
    """Write credentials JSON with 0600 permissions."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    expires = datetime.fromtimestamp(now.timestamp() + ttl, tz=timezone.utc)

    creds = {
        "access_token": token,
        "token_type": "bearer",
        "email": email,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }

    fp = _credentials_path(path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(creds, indent=2))
    os.chmod(fp, 0o600)
    logger.debug("Credentials saved to %s", fp)


def load_credentials(path: str | None = None) -> Credentials | None:
    """Read and validate stored credentials. Returns None if missing or malformed."""
    fp = _credentials_path(path)
    if not fp.exists():
        return None
    try:
        data = json.loads(fp.read_text())
        return Credentials(**data)
    except Exception as e:
        logger.warning("Failed to load credentials from %s: %s", fp, e)
        return None


def clear_credentials(path: str | None = None) -> None:
    """Delete the credentials file."""
    fp = _credentials_path(path)
    if fp.exists():
        fp.unlink()
        logger.debug("Credentials cleared: %s", fp)


def is_token_expired(creds: Credentials) -> bool:
    """Check whether the token has expired based on the stored expires_at."""
    if not creds.expires_at:
        return False  # no expiry info — assume valid
    try:
        from datetime import datetime, timezone

        expires = datetime.fromisoformat(creds.expires_at)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires
    except Exception:
        return False


def get_access_token(path: str | None = None) -> str | None:
    """Load credentials and return the token if still valid, else None."""
    creds = load_credentials(path)
    if creds is None:
        return None
    if is_token_expired(creds):
        logger.debug("Token expired for %s", creds.email)
        return None
    return creds.access_token
