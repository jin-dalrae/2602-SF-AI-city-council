"""Findings routes: history snapshot + SSE live stream."""

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from backend.events import broadcaster
from backend.services import storage
from backend.state import findings_store

router = APIRouter(prefix="/api/findings")


@router.get("/history")
async def get_findings_history(limit: int = 5000):
    history = storage.get_history(limit=limit)
    return JSONResponse(content={"history": history})


@router.get("")
async def stream_findings(request: Request):
    """SSE: replay current findings, then stream live events until disconnect."""
    subscriber_queue = broadcaster.subscribe()

    async def event_generator():
        try:
            for key, finding in findings_store.items():
                if key.startswith("_"):
                    continue
                yield {"event": "finding", "data": json.dumps(finding)}

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(subscriber_queue.get(), timeout=30.0)
                    yield {"event": event["type"], "data": json.dumps(event["data"])}
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            broadcaster.unsubscribe(subscriber_queue)

    return EventSourceResponse(event_generator())
