"""FastAPI app entry point.

Lifespan owns: storage init, shared client init, finding-snapshot persistence,
broadcaster + auto-save background tasks, agent lifecycle. Routes are mounted
from `backend/api/`.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import deps
from backend.api import agents_router, email_router, findings_router
from backend.api.agents import start_all_agents, stop_all_agents
from backend.events import listen_and_broadcast
from backend.services import storage
from backend.state import findings_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agents")


async def _auto_save_loop() -> None:
    while True:
        await asyncio.sleep(30)
        if findings_store:
            await storage.save_findings(findings_store)
            logger.info(f"💾 Auto-saved {len(findings_store)} findings to disk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.init_storage()
    await deps.init_clients()

    loaded = storage.load_findings()
    if loaded:
        findings_store.update(loaded)
        logger.info(f"📂 Loaded {len(loaded)} previous findings from disk")

    save_task = asyncio.create_task(_auto_save_loop())
    broadcast_task = asyncio.create_task(listen_and_broadcast())

    await start_all_agents()

    yield

    logger.info("🛑 Shutting down server...")
    await storage.save_findings(findings_store)
    save_task.cancel()
    broadcast_task.cancel()
    await stop_all_agents()
    await deps.close_clients()


app = FastAPI(title="AI City Council", lifespan=lifespan)

static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(agents_router)
app.include_router(findings_router)
app.include_router(email_router)


@app.get("/")
async def serve_dashboard():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(str(static_dir / "favicon.ico"))


@app.get("/terms")
async def terms():
    return FileResponse(str(static_dir / "terms.html"))


@app.get("/privacy")
async def privacy():
    return FileResponse(str(static_dir / "privacy.html"))
