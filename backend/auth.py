"""Bearer-token auth for mutating endpoints.

Set API_AUTH_TOKEN in the environment to enable. If unset, protected
endpoints return 503 — we fail loud rather than silently disabling auth,
so a misconfigured deploy never exposes start/stop/email routes.
"""

import os
import secrets

from fastapi import Header, HTTPException


def _expected_token() -> str | None:
    tok = os.getenv("API_AUTH_TOKEN", "").strip()
    return tok or None


async def require_token(authorization: str | None = Header(default=None)) -> None:
    expected = _expected_token()
    if expected is None:
        raise HTTPException(
            status_code=503,
            detail="API_AUTH_TOKEN not configured on the server.",
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    presented = authorization.split(" ", 1)[1].strip()
    if not secrets.compare_digest(presented, expected):
        raise HTTPException(status_code=403, detail="Invalid token.")
