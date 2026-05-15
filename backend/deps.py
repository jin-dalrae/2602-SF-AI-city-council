"""Process-wide singleton clients.

Owned by the FastAPI lifespan: `init_clients()` runs at startup, `close_clients()`
on shutdown. Agents pull from here instead of constructing their own HTTP
clients per instance.
"""

from __future__ import annotations

import os
from typing import Optional

from backend.services.socrata import SocrataClient

# Composio is imported lazily — it's not used in tests and pulls in langchain.
_composio_client = None
_socrata_client: Optional[SocrataClient] = None


def socrata() -> SocrataClient:
    if _socrata_client is None:
        raise RuntimeError("Socrata client not initialized. Call init_clients() first.")
    return _socrata_client


def composio():
    """Returns the shared Composio client, or None if no API key is configured."""
    return _composio_client


async def init_clients() -> None:
    global _socrata_client, _composio_client
    _socrata_client = SocrataClient()

    api_key = os.getenv("COMPOSIO_API_KEY", "").strip()
    if api_key:
        from composio import Composio
        from composio_langchain import LangchainProvider

        _composio_client = Composio(api_key=api_key, provider=LangchainProvider())


async def close_clients() -> None:
    global _socrata_client, _composio_client
    if _socrata_client is not None:
        await _socrata_client.close()
        _socrata_client = None
    _composio_client = None
