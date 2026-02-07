import asyncio
import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from backend.agents import ALL_AGENTS, NEWS_AGENT
from backend.email_agent import draft_email
from backend.services import storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("agents")

# Shared state
findings_store: dict[str, dict] = {}
event_queue: asyncio.Queue = asyncio.Queue()
agent_tasks: list[asyncio.Task] = []
agent_status: dict[str, dict] = {}  # Track agent status


def update_agent_status(agent_name: str, status: str, details: str = ""):
    """Update the status of an agent."""
    agent_status[agent_name] = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "details": details,
    }
    logger.info(f"🤖 [{agent_name}] {status} {details}")


async def _launch_agent(AgentClass, delay: int):
    """Launch an agent with a staggered start delay."""
    agent_name = AgentClass.name if hasattr(AgentClass, 'name') else AgentClass.__name__
    update_agent_status(agent_name, "⏳ WAITING", f"Starting in {delay}s...")
    await asyncio.sleep(delay)
    
    agent = AgentClass(findings_store, event_queue)
    update_agent_status(agent_name, "🟢 RUNNING", "Agent loop started")
    
    try:
        await agent.run_loop(interval=60)
    except asyncio.CancelledError:
        update_agent_status(agent_name, "🔴 STOPPED", "Agent cancelled")
        raise
    except Exception as e:
        update_agent_status(agent_name, "❌ ERROR", str(e)[:100])
        raise


async def _launch_news_agent():
    """Launch the SF News Agent with no delay (runs first to provide context)."""
    agent_name = NEWS_AGENT.name
    update_agent_status(agent_name, "🟢 RUNNING", "News agent started first")
    
    agent = NEWS_AGENT(findings_store, event_queue)
    try:
        await agent.run_loop(interval=90)
    except asyncio.CancelledError:
        update_agent_status(agent_name, "🔴 STOPPED", "Agent cancelled")
        raise
    except Exception as e:
        update_agent_status(agent_name, "❌ ERROR", str(e)[:100])
        raise


async def _auto_save_loop():
    """Periodically save findings to disk."""
    while True:
        await asyncio.sleep(30)  # Save every 30 seconds
        if findings_store:
            storage.save_findings(findings_store)
            logger.info(f"💾 Auto-saved {len(findings_store)} findings to disk")


async def start_all_agents():
    """Start all agents if not already running."""
    global agent_tasks
    if agent_tasks:
        logger.info("⚠️ Agents are already running")
        return False
        
    logger.info("🚀 Starting all agents...")
    news_task = asyncio.create_task(_launch_news_agent())
    agent_tasks.append(news_task)
    
    for i, AgentClass in enumerate(ALL_AGENTS):
        task = asyncio.create_task(_launch_agent(AgentClass, delay=(i + 1) * 5))
        agent_tasks.append(task)
    
    logger.info(f"✅ Launched {len(agent_tasks)} agent tasks")
    return True


async def stop_all_agents():
    """Stop all running agents."""
    global agent_tasks
    if not agent_tasks:
        logger.info("⚠️ No agents are currently running")
        return False
        
    logger.info("🛑 Stopping all agents...")
    for task in agent_tasks:
        task.cancel()
    
    # Wait for tasks to be cancelled
    if agent_tasks:
        await asyncio.gather(*agent_tasks, return_exceptions=True)
    
    agent_tasks = []
    # Set status to stopped for all
    for name in agent_status:
        if agent_status[name]["status"] != "❌ ERROR":
            agent_status[name]["status"] = "🔴 STOPPED"
            
    logger.info("🔴 All agents stopped")
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load previous findings from disk
    loaded = storage.load_findings()
    if loaded:
        findings_store.update(loaded)
        logger.info(f"📂 Loaded {len(loaded)} previous findings from disk")
    
    # Start auto-save task
    save_task = asyncio.create_task(_auto_save_loop())
    
    # Startup: launch agents
    await start_all_agents()
    
    yield
    
    # Shutdown: save findings and cancel all agents
    logger.info("🛑 Shutting down server...")
    storage.save_findings(findings_store)
    save_task.cancel()
    await stop_all_agents()


app = FastAPI(title="AI City Council", lifespan=lifespan)


# Serve static files
static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_dashboard():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/favicon.ico")
async def serve_favicon():
    return FileResponse(str(static_dir / "favicon.ico"))



@app.get("/api/findings/latest")
async def get_latest_findings():
    # Filter out internal keys (like _news_headlines)
    results = [v for k, v in findings_store.items() if not k.startswith("_")]
    return JSONResponse(content=results)


@app.get("/api/agents/status")
async def get_agent_status():
    """Get the current status of all agents."""
    return JSONResponse(content={
        "agents": agent_status,
        "is_running": len(agent_tasks) > 0,
        "total_findings": len([k for k in findings_store if not k.startswith("_")]),
        "server_time": datetime.now(timezone.utc).isoformat(),
    })


@app.post("/api/agents/start")
async def api_start_agents():
    success = await start_all_agents()
    return JSONResponse(content={"success": success, "message": "Agents started" if success else "Already running"})


@app.post("/api/agents/stop")
async def api_stop_agents():
    success = await stop_all_agents()
    return JSONResponse(content={"success": success, "message": "Agents stopped" if success else "Not running"})

@app.get("/api/findings")
async def stream_findings(request: Request):
    async def event_generator():
        # First send all current findings
        for key, finding in findings_store.items():
            if key.startswith("_"):
                continue
            yield {"event": "finding", "data": json.dumps(finding)}

        # Then stream new updates
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                yield {"event": "finding", "data": json.dumps(event["data"])}
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": "{}"}

    return EventSourceResponse(event_generator())


class EmailRequest(BaseModel):
    agent_name: str
    citizen_name: str = ""
    desired_outcome: str = ""
    include_admin: bool = True


class SendEmailRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str


@app.post("/api/email/draft")
async def create_email_draft(req: EmailRequest):
    finding = findings_store.get(req.agent_name)
    if not finding:
        return JSONResponse(
            status_code=404,
            content={"error": f"No findings for agent: {req.agent_name}"},
        )
    result = await draft_email(
        agent_finding=finding,
        citizen_name=req.citizen_name,
        desired_outcome=req.desired_outcome,
        include_admin=req.include_admin,
    )
    return JSONResponse(content=result)


@app.post("/api/email/send")
async def api_send_email(req: SendEmailRequest):
    from backend.email_agent import send_email
    result = await send_email(req.recipient_email, req.subject, req.body)
    if result.get("success"):
        return JSONResponse(content=result)
    else:
        return JSONResponse(status_code=500, content=result)
