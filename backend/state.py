"""Process-wide mutable state shared by API routes and the agent loop.

Lives in one module so routes don't need to thread state through FastAPI's
DI system. The lifespan owns lifecycle; routes only read/write.
"""

import asyncio
from datetime import datetime, timezone


findings_store: dict[str, dict] = {}
event_queue: asyncio.Queue = asyncio.Queue()
agent_tasks: list[asyncio.Task] = []
agent_status: dict[str, dict] = {}


def update_agent_status(agent_name: str, status: str, details: str = "") -> None:
    agent_status[agent_name] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "details": details,
    }
