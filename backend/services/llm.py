import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = """You are an Expert Data Analyst and AI civic strategist for San Francisco citizens.
You analyze city data and produce structured findings with high temporal awareness.
You have the capability to take REAL-WORLD ACTIONS via Composio (e.g. creating GitHub Civic Tickets) when issues are severe.

TRAIT: DATA ANALYST
- Do not just report raw totals. Breakdown data by periods (Month, Week, or Day) where possible.
- Identify trends (increasing vs decreasing) rather than static snapshots.
- If a number is exceptionally high, compare it to historical averages or previous periods to provide context.

ALWAYS respond with valid JSON matching this schema:
{
  "issue_title": "Short title of the detected issue",
  "severity": "low" | "medium" | "high" | "critical",
  "summary": "2-3 sentence summary of the issue, emphasizing changes over time",
  "key_metrics": [{"label": "metric name/period", "value": "metric value"}],
  "evidence": ["bullet point evidence items highlighting specific trends"],
  "solution": "Detailed policy recommendation based on the identified trend (2-4 sentences)",
  "affected_neighborhoods": ["list of SF neighborhoods if applicable"]
}

Be specific with numbers and data. Focus on actionable insights for NGO advocacy."""


async def get_embedding(text: str) -> list[float]:
    """Generate embeddings for text using Gemini."""
    try:
        response = await asyncio.to_thread(
            lambda: client.models.embed_content(
                model="text-embedding-004",
                contents=text,
            )
        )
        return response.embeddings[0].values
    except:
        return []


async def analyze_data(agent_name: str, data_summary: str, prompt: str, traits: list[str] = None, memories: list[str] = None) -> dict:
    custom_instruction = SYSTEM_PROMPT
    if traits:
        custom_instruction += "\n\nACTIVE EXPERT TRAITS:\n" + "\n".join(f"- {t}" for t in traits)
    
    memory_context = ""
    if memories:
        memory_context = "\n\nRECALLED EPISODIC MEMORIES (From past cycles):\n" + "\n".join(f"- {m}" for m in memories)

    full_prompt = f"""Agent: {agent_name}

{memory_context}

Data Summary:
{data_summary}

Analysis Task:
{prompt}"""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=custom_instruction,
                temperature=0.3,
            ),
        )
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        if text.startswith("json"):
            text = text[4:].strip()
        return json.loads(text)


async def evolve_brain(agent_name: str, current_traits: list[str], finding: dict) -> dict:
    """
    LLM evaluates the agent's research and decides if it should update its traits 
    or log a 'learning' message about its own process.
    """
    prompt = f"""You are the internal 'Brain Controller' for an AI agent named {agent_name}.
Current traits: {current_traits}
Latest finding: {json.dumps(finding)}

Analyze if the agent discovered a new analytical pattern or if it should evolve its traits.
Return JSON ONLY:
{{
  "learning_message": "A 1-sentence message about what the agent learned about the city or its data (e.g. 'I noticed a strong correlation between road repairs and neighborhood income levels.')",
  "new_trait": "Optional: a new specific expertise title (e.g. 'Pothole Density Specialist')",
  "evolved_thought": "Short internal reflection on how to improve next analysis (e.g. 'I need to cross-reference budget data more closely with public works requests.')"
}}
"""
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7)
        )
        return json.loads(response.text)
    except:
        return {"learning_message": "Research cycle complete.", "new_trait": None, "evolved_thought": "Continuing monitoring."}
    except (json.JSONDecodeError, Exception) as e:
        err_str = str(e)[:150]
        is_key_issue = "leaked" in err_str.lower() or "permission" in err_str.lower() or "403" in err_str
        return {
            "issue_title": f"{agent_name} - Data Collected (LLM Unavailable)" if is_key_issue else f"{agent_name} Analysis Update",
            "severity": "medium",
            "summary": f"Data successfully fetched from SF Open Data. LLM analysis pending — {'API key needs replacement' if is_key_issue else 'will retry next cycle'}.",
            "key_metrics": [],
            "evidence": [line.strip() for line in data_summary.split("\n") if line.strip()][:8],
            "solution": "Replace GEMINI_API_KEY in .env with a new key from https://aistudio.google.com/apikey" if is_key_issue else "Retry analysis on next cycle.",
            "affected_neighborhoods": [],
        }


async def generate_collaboration(agent_a: str, agent_b: str, finding_a: dict, finding_b: dict) -> dict:
    prompt = f"""Two city agents have related findings. Generate a combined analysis.

Agent A ({agent_a}): {json.dumps(finding_a, indent=2)}
Agent B ({agent_b}): {json.dumps(finding_b, indent=2)}

Produce a combined finding showing how these issues are interconnected and a joint policy recommendation."""

    return await analyze_data(
        f"{agent_a} + {agent_b}",
        "Cross-agent collaboration analysis",
        prompt,
    )
