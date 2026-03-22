"""HTTP client for device-flow authentication.

Flow:
1. POST /v1/auth/device — get a device_code and login URL
2. Open the login URL in the user's browser
3. Poll POST /v1/auth/device/token until the user completes login
4. Receive access_token, email, and model credentials
"""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://api.ignite-ember.sh"
_TIMEOUT = 15.0
_POLL_INTERVAL = 2.0
_MAX_POLL_TIME = 300  # 5 minutes


async def request_device_code(api_url: str = DEFAULT_API_URL) -> dict:
    """POST /v1/auth/device — initiate device login flow.

    Returns dict with:
        device_code: str — opaque code for polling
        login_url: str — URL to open in the browser
        expires_in: int — seconds until the code expires
    """
    url = f"{api_url.rstrip('/')}/v1/auth/device"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url)
        resp.raise_for_status()
        return resp.json()


async def poll_for_token(
    device_code: str,
    api_url: str = DEFAULT_API_URL,
    poll_interval: float = _POLL_INTERVAL,
    max_poll_time: float = _MAX_POLL_TIME,
) -> dict:
    """Poll POST /v1/auth/device/token until the user completes login.

    Returns dict with:
        access_token: str
        email: str
        model_api_key: str
        model_url: str
        model_name: str (optional, defaults to MiniMax-M2.7)

    Raises TimeoutError if the user doesn't complete login in time.
    Raises httpx.HTTPStatusError on server errors.
    """
    url = f"{api_url.rstrip('/')}/v1/auth/device/token"
    elapsed = 0.0

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        while elapsed < max_poll_time:
            resp = await client.post(url, json={"device_code": device_code})

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 202:
                # Authorization pending — user hasn't completed login yet
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue

            # Unexpected status
            resp.raise_for_status()

    raise TimeoutError("Login timed out — please try again")
