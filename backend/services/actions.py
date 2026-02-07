import os
import asyncio
from composio import Composio
from composio_langchain import LangchainProvider
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
        # Initialize Composio with LangchainProvider for version 0.11.0+
        # This replaces the old ComposioToolSet approach.
        composio = Composio(api_key=api_key, provider=LangchainProvider())
        
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

        # For demonstration purposes, we'll log this to the agent's brain
        action_log = {
            "status": "triggered",
            "tool": "GitHub",
            "action": "CREATE_ISSUE",
            "title": issue_title
        }
        
        # We wrap the synchronous Composio call in a thread
        # In 0.11.0, we use composio.tools.execute or simply composio.execute
        # Try multiple possible slugs as Composio versions/tools can vary
        slugs_to_try = ["GITHUB_CREATE_ISSUE", "github_issues_create", "github_create_issue"]
        result = None
        last_err = None
        
        for slug in slugs_to_try:
            try:
                result = await asyncio.to_thread(
                    lambda: composio.tools.execute(
                        slug=slug,
                        arguments={
                            "owner": "jin-dalrae",
                            "repo": "2602-SF-AI-city-council",
                            "title": issue_title,
                            "body": issue_body
                        },
                        user_id="default"
                    )
                )
                if result:
                    break
            except Exception as e:
                last_err = e
                continue
        
        if not result and last_err:
            raise last_err
        
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

