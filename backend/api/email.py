"""Email draft + send routes (token-protected)."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.auth import require_token
from backend.services.email_drafting import draft_email, send_email
from backend.state import findings_store

router = APIRouter(prefix="/api/email")


class EmailRequest(BaseModel):
    agent_name: str
    citizen_name: str = ""
    desired_outcome: str = ""
    include_admin: bool = True


class SendEmailRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str


def _lookup_finding(agent_name: str) -> dict | None:
    """Findings are stored as `{agent}:{title}`. Accept either the full key or
    just the agent name (most common request from the dashboard)."""
    finding = findings_store.get(agent_name)
    if finding:
        return finding
    key = next((k for k in findings_store if k.startswith(f"{agent_name}:")), None)
    return findings_store.get(key) if key else None


@router.post("/draft", dependencies=[Depends(require_token)])
async def create_email_draft(req: EmailRequest):
    finding = _lookup_finding(req.agent_name)
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


@router.post("/send", dependencies=[Depends(require_token)])
async def api_send_email(req: SendEmailRequest):
    result = await send_email(req.recipient_email, req.subject, req.body)
    if result.get("success"):
        return JSONResponse(content=result)
    return JSONResponse(status_code=500, content=result)
