import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = """You are an AI civic analyst for San Francisco NGOs.
You analyze city data and produce structured findings.

ALWAYS respond with valid JSON matching this schema:
{
  "issue_title": "Short title of the detected issue",
  "severity": "low" | "medium" | "high" | "critical",
  "summary": "2-3 sentence summary of the issue",
  "key_metrics": [{"label": "metric name", "value": "metric value"}],
  "evidence": ["bullet point evidence items"],
  "solution": "Detailed policy recommendation (2-4 sentences)",
  "affected_neighborhoods": ["list of SF neighborhoods if applicable"]
}

Be specific with numbers and data. Focus on actionable insights for NGO advocacy."""


async def analyze_data(agent_name: str, data_summary: str, prompt: str) -> dict:
    full_prompt = f"""Agent: {agent_name}

Data Summary:
{data_summary}

Analysis Task:
{prompt}"""

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
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
    except (json.JSONDecodeError, Exception) as e:
        return {
            "issue_title": f"{agent_name} Analysis Update",
            "severity": "low",
            "summary": f"Data collected but analysis encountered an issue: {str(e)[:100]}",
            "key_metrics": [],
            "evidence": [data_summary[:200]],
            "solution": "Retry analysis on next cycle.",
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
