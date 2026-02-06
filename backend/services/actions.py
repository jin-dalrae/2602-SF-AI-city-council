import os
import asyncio
from composio_langchain import ComposioToolSet, App, Action
from backend.services import llm

async def trigger_civic_action(agent_name: str, finding: dict) -> dict:
    """
    Use Composio to take a real-world action (e.g. creating a GitHub issue) 
    when an agent detects a high-severity civic issue.
    """
    severity = finding.get("severity", "low").lower()
    if severity not in ["high", "critical", "urgent"]:
        return {"status": "skipped", "message": "Severity too low for automated action."}

    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        return {"status": "error", "message": "COMPOSIO_API_KEY not found."}

    try:
        # For the hackathon, we'll demonstrate a GitHub issue creation as a 'Civic Ticket'
        # In a real scenario, this would go to a city-managed repo.
        toolset = ComposioToolSet(api_key=api_key)
        
        issue_title = f"[CIVIC-ISSUE] {finding.get('issue_title', 'Alert from ' + agent_name)}"
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

        # We'll use the 'GITHUB_CREATE_ISSUE' action
        # Note: This assumes the user has connected GitHub to Composio.
        # If not, it will return an error, which we handle.
        
        # For demonstration purposes, we'll also log this to the agent's brain
        action_log = {
            "status": "triggered",
            "tool": "GitHub",
            "action": "CREATE_ISSUE",
            "title": issue_title
        }
        
        # We wrap the synchronous Composio call in a thread
        result = await asyncio.to_thread(
            lambda: toolset.execute_action(
                action=Action.GITHUB_CREATE_ISSUE,
                params={
                    "owner": "jin-dalrae", # Fallback to a demo repo or user repo
                    "repo": "2602-SF-AI-city-council",
                    "title": issue_title,
                    "body": issue_body
                }
            )
        )
        
        return {
            "status": "success",
            "result": result,
            "action_log": action_log
        }
    except Exception as e:
        print(f"[Composio] Action failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "action_log": {"status": "failed", "error": str(e)}
        }
