import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YOU_COM_API_KEY", "").strip()
AGENTS_URL = "https://api.you.com/v1/agents/runs"


async def search_context(query: str) -> str:
    """Search You.com for policy context and news using the agents API."""
    if not API_KEY:
        return "You.com API key not configured."

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "agent": "advanced",
        "input": query,
        "stream": False,
        "tools": [{"type": "research"}],
        "verbosity": "low",
        "workflow_config": {"max_workflow_steps": 3},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(AGENTS_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Extract the response text
            answer = data.get("answer", "")
            if not answer:
                # Try to extract from different response formats
                for key in ("text", "content", "output", "response"):
                    if key in data:
                        answer = data[key]
                        break
            if not answer:
                answer = json.dumps(data)[:500]
            # Split into bullet points
            lines = [l.strip() for l in answer.split("\n") if l.strip() and len(l.strip()) > 10]
            return "\n".join(f"- {l}" for l in lines[:5])
        except httpx.HTTPStatusError:
            # Fall back to streaming mode
            try:
                payload["stream"] = True
                resp = await client.post(AGENTS_URL, headers=headers, json=payload)
                resp.raise_for_status()
                text_parts = []
                for line in resp.text.split("\n"):
                    if line.startswith("data: "):
                        try:
                            event_data = json.loads(line[6:])
                            if "answer" in event_data:
                                text_parts.append(event_data["answer"])
                        except json.JSONDecodeError:
                            pass
                if text_parts:
                    answer = text_parts[-1]  # Last answer is the most complete
                    lines = [l.strip() for l in answer.split("\n") if l.strip() and len(l.strip()) > 10]
                    return "\n".join(f"- {l}" for l in lines[:5])
                return "No relevant results found."
            except Exception as e:
                return f"Search error: {str(e)[:100]}"
        except Exception as e:
            return f"Search error: {str(e)[:100]}"
