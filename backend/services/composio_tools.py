import asyncio
import time

from backend import deps
from backend.config import CIVIC_ACTION_COOLDOWN_SECONDS, SEVERITY_ACTION_THRESHOLD

# In-process dedup: (agent_name, issue_title) -> last-triggered epoch seconds.
# Prevents the same finding from spawning duplicate GitHub issues every loop.
_recent_triggers: dict[tuple[str, str], float] = {}


def _is_on_cooldown(agent_name: str, issue_title: str) -> bool:
    key = (agent_name, issue_title)
    last = _recent_triggers.get(key)
    if last is None:
        return False
    return (time.monotonic() - last) < CIVIC_ACTION_COOLDOWN_SECONDS


def _mark_triggered(agent_name: str, issue_title: str) -> None:
    _recent_triggers[(agent_name, issue_title)] = time.monotonic()


async def trigger_civic_action(agent_name: str, finding: dict) -> dict:
    """
    Use Composio to take a real-world action (e.g. creating a GitHub issue)
    when an agent detects a high-severity civic issue.
    """
    severity = finding.get("severity", "low").lower()
    if severity not in SEVERITY_ACTION_THRESHOLD:
        return {"status": "skipped", "message": "Severity too low for automated action."}

    issue_title = finding.get("issue_title") or f"Alert from {agent_name}"
    if _is_on_cooldown(agent_name, issue_title):
        return {"status": "skipped", "message": "On cooldown (already triggered recently)."}

    composio = deps.composio()
    if composio is None:
        return {"status": "error", "message": "Composio client not configured."}

    try:
        github_title = f"[CIVIC-ISSUE] {issue_title}"
        issue_body = f"""
### Citizen Advocacy Alert: {agent_name}
**Severity**: {finding.get('severity', 'N/A')}
**Summary**: {finding.get('summary', 'N/A')}

**Evidence**:
{", ".join(finding.get('evidence', []))}

**Recommended Solution**:
{finding.get('solution', 'N/A')}

---
*Reported automatically by AI City Council Dashboard*
"""

        action_log = {
            "status": "triggered",
            "tool": "GitHub",
            "action": "CREATE_ISSUE",
            "title": github_title,
        }

        # Composio tool slugs vary by version; try the known options.
        slugs_to_try = ["GITHUB_CREATE_ISSUE", "github_issues_create", "github_create_issue"]
        result = None
        last_err: Exception | None = None

        for slug in slugs_to_try:
            try:
                result = await asyncio.to_thread(
                    composio.tools.execute,
                    slug=slug,
                    arguments={
                        "owner": "jin-dalrae",
                        "repo": "2602-SF-AI-city-council",
                        "title": github_title,
                        "body": issue_body,
                    },
                    user_id="default",
                )
                if result:
                    break
            except Exception as e:
                last_err = e
                continue

        if not result and last_err:
            raise last_err

        _mark_triggered(agent_name, issue_title)
        return {"status": "success", "result": result, "action_log": action_log}
    except Exception as e:
        print(f"[Composio] Action failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "action_log": {"status": "failed", "error": str(e)},
        }

