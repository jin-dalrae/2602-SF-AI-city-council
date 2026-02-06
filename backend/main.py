import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from backend.agents import ALL_AGENTS, NEWS_AGENT
from backend.email_agent import draft_email

# Shared state
findings_store: dict[str, dict] = {}
event_queue: asyncio.Queue = asyncio.Queue()
agent_tasks: list[asyncio.Task] = []


async def _launch_agent(AgentClass, delay: int):
    """Launch an agent with a staggered start delay."""
    await asyncio.sleep(delay)
    agent = AgentClass(findings_store, event_queue)
    await agent.run_loop(interval=60)


async def _launch_news_agent():
    """Launch the SF News Agent with no delay (runs first to provide context)."""
    agent = NEWS_AGENT(findings_store, event_queue)
    await agent.run_loop(interval=90)  # Slightly longer interval for news


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch news agent first, then data agents with 5s stagger
    # News agent runs first to provide context for other agents
    news_task = asyncio.create_task(_launch_news_agent())
    agent_tasks.append(news_task)
    
    for i, AgentClass in enumerate(ALL_AGENTS):
        task = asyncio.create_task(_launch_agent(AgentClass, delay=(i + 1) * 5))
        agent_tasks.append(task)
    yield
    # Shutdown: cancel all agents
    for task in agent_tasks:
        task.cancel()


app = FastAPI(title="AI City Council", lifespan=lifespan)

# Serve static files
static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_dashboard():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/api/findings/latest")
async def get_latest_findings():
    return JSONResponse(content=list(findings_store.values()))


@app.get("/api/findings")
async def stream_findings(request: Request):
    async def event_generator():
        # First send all current findings
        for finding in findings_store.values():
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
    ngo_name: str
    desired_outcome: str
    context: str = ""
    contact_person: str = ""


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
        ngo_name=req.ngo_name,
        desired_outcome=req.desired_outcome,
        context=req.context,
        contact_person=req.contact_person,
    )
    return JSONResponse(content=result)
