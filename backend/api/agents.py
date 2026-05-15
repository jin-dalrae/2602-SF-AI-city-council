"""Agent lifecycle routes + the in-process launcher."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.agents import ALL_AGENTS, NEWS_AGENT
from backend.auth import require_token
from backend.config import AGENT_LOOP_INTERVAL, NEWS_LOOP_INTERVAL
from backend.services import storage
from backend.state import (
    agent_status,
    agent_tasks,
    event_queue,
    findings_store,
    update_agent_status,
)

logger = logging.getLogger("agents")
router = APIRouter(prefix="/api/agents")


async def _launch_agent(AgentClass, delay: int, interval: int) -> None:
    name = getattr(AgentClass, "name", AgentClass.__name__)
    update_agent_status(name, "⏳ WAITING", f"Starting in {delay}s...")
    logger.info(f"🤖 [{name}] WAITING (starting in {delay}s)")
    await asyncio.sleep(delay)

    agent = AgentClass(findings_store, event_queue)
    update_agent_status(name, "🟢 RUNNING", "Agent loop started")
    logger.info(f"🤖 [{name}] RUNNING")

    try:
        await agent.run_loop(interval=interval)
    except asyncio.CancelledError:
        update_agent_status(name, "🔴 STOPPED", "Agent cancelled")
        raise
    except Exception as e:
        update_agent_status(name, "❌ ERROR", str(e)[:100])
        logger.exception(f"[{name}] crashed")
        raise


async def start_all_agents() -> bool:
    if agent_tasks:
        logger.info("⚠️ Agents are already running")
        return False

    logger.info("🚀 Starting all agents...")
    # News agent first (no stagger) — its output is consumed by sibling agents.
    agent_tasks.append(
        asyncio.create_task(_launch_agent(NEWS_AGENT, delay=0, interval=NEWS_LOOP_INTERVAL))
    )
    for i, AgentClass in enumerate(ALL_AGENTS):
        agent_tasks.append(
            asyncio.create_task(
                _launch_agent(AgentClass, delay=(i + 1) * 5, interval=AGENT_LOOP_INTERVAL)
            )
        )
    logger.info(f"✅ Launched {len(agent_tasks)} agent tasks")
    return True


async def stop_all_agents() -> bool:
    if not agent_tasks:
        logger.info("⚠️ No agents are currently running")
        return False

    logger.info("🛑 Stopping all agents...")
    for task in agent_tasks:
        task.cancel()
    await asyncio.gather(*agent_tasks, return_exceptions=True)
    agent_tasks.clear()

    for name in agent_status:
        if agent_status[name]["status"] != "❌ ERROR":
            agent_status[name]["status"] = "🔴 STOPPED"

    logger.info("🔴 All agents stopped")
    return True


@router.get("/status")
async def get_agent_status_route():
    history = storage.get_history(limit=1000)
    return JSONResponse(
        content={
            "agents": agent_status,
            "is_running": len(agent_tasks) > 0,
            "total_findings": len([k for k in findings_store if not k.startswith("_")]),
            "historical_count": len(history),
            "server_time": datetime.now(timezone.utc).isoformat(),
        }
    )


@router.post("/start", dependencies=[Depends(require_token)])
async def api_start_agents():
    success = await start_all_agents()
    return JSONResponse(
        content={"success": success, "message": "Agents started" if success else "Already running"}
    )


@router.post("/stop", dependencies=[Depends(require_token)])
async def api_stop_agents():
    success = await stop_all_agents()
    return JSONResponse(
        content={"success": success, "message": "Agents stopped" if success else "Not running"}
    )
