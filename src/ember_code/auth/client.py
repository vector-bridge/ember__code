"""HTTP client for OTP authentication endpoints."""

import logging

import httpx

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://api.ignite-ember.sh"
_TIMEOUT = 15.0


async def request_sign_in_code(api_url: str = DEFAULT_API_URL, email: str = "") -> str:
    """POST /v1/send-sign-in-code — request an OTP code via email.

    Returns a status message from the server, or raises on failure.
    """
    url = f"{api_url.rstrip('/')}/v1/send-sign-in-code"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json={"email": email})
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", "Code sent")


async def sign_in_with_code(
    api_url: str = DEFAULT_API_URL,
    email: str = "",
    code: str = "",
) -> dict:
    """POST /v1/sign-in-with-code — exchange email + OTP for a bearer token.

    Returns the response dict containing ``access_token`` and ``token_type``.
    Raises ``httpx.HTTPStatusError`` on failure.
    """
    url = f"{api_url.rstrip('/')}/v1/sign-in-with-code"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json={"email": email, "code": code})
        resp.raise_for_status()
        return resp.json()
