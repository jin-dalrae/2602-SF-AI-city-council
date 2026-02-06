import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YOU_COM_API_KEY", "").strip()
SEARCH_URL = "https://ydc-index.io/v1/search"


async def search_context(query: str) -> str:
    """Search You.com for policy context and news using the Search API."""
    if not API_KEY:
        return "You.com API key not configured."

    headers = {
        "X-API-Key": API_KEY,
    }
    params = {
        "query": query,
        "count": 5
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(SEARCH_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            results = data.get("results", {})
            web_results = results.get("web", [])
            
            if not web_results:
                return "No relevant results found."
                
            formatted_lines = []
            for res in web_results[:5]:
                title = res.get("title", "No Title")
                # Use description or first snippet
                snippet = res.get("description", "")
                if not snippet and res.get("snippets"):
                    snippet = res.get("snippets")[0]
                
                if snippet:
                    formatted_lines.append(f"- {title}: {snippet}")
                else:
                    formatted_lines.append(f"- {title}")
                    
            return "\n".join(formatted_lines)
            
        except Exception as e:
            return f"Search error: {str(e)[:100]}"
