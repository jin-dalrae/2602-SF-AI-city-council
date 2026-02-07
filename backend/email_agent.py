import os
import json
from dotenv import load_dotenv

from composio import Composio
from composio_langchain import LangchainProvider
import asyncio
from backend.services import llm

load_dotenv()

COMPOSIO_API_KEY = "ak_zMx6z54f0h6_e1BApUnw"


async def draft_email(
    agent_finding: dict,
    citizen_name: str,
    desired_outcome: str,
    include_admin: bool = True
) -> dict:
    """Generate a professional email draft for city officials from a citizen using Gemini."""
    officials = agent_finding.get("officials", [])
    to_addresses = [o.get("email", "") for o in officials if o.get("email")]
    cc_addresses = []
    
    if include_admin:
        cc_addresses.append("carmen.chu@sfgov.org")

    to_names = [f"{o.get('name', '')} ({o.get('title', '')})" for o in officials]
    if include_admin:
        to_names.append("Carmen Chu (City Administrator)")

    prompt = f"""Draft a professional email from a San Francisco citizen to a city official.

Citizen Name: {citizen_name or 'A concerned resident'}
Recipients: {', '.join(to_names)}
Desired Outcome: {desired_outcome or agent_finding.get('solution', 'Action on this issue')}

Issue Found by AI Analysis:
Title: {agent_finding.get('issue_title', 'N/A')}
Summary: {agent_finding.get('summary', 'N/A')}
Evidence: {json.dumps(agent_finding.get('evidence', []))}
Recommended Solution: {agent_finding.get('solution', 'N/A')}

Write a formal but compelling email that:
1. Introduces the sender as a San Francisco resident
2. References the specific data findings (minimum 2 data citations)
3. Proposes the desired outcome or the AI-recommended solution
4. Requests a response or specific action
5. Includes a 'Evidence Data Sources' footer section with relevant URLs from SF Open Data
6. Is respectful and professional

Return JSON with these fields:
- "subject": email subject line
- "body": full email body text (including the Evidence Data Sources footer)
- "to": list of recipient email addresses
"""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are an expert civic communications assistant. Always respond with valid JSON matching the requested structure.",
                temperature=0.4,
            ),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        if text.startswith("json"):
            text = text[4:].strip()
        
        raw_result = json.loads(text)
        
        # Format as per PRD Section 4.4
        data_sources = []
        if "evidence" in agent_finding:
            for item in agent_finding["evidence"][:2]: # PRD requires min 2
                data_sources.append({
                    "dataset": agent_finding.get("agent_name", "SF Open Data"),
                    "url": "https://data.sfgov.org" # Generic fallback
                })

        return {
            "email_draft": {
                "subject": raw_result.get("subject", f"Priority: {agent_finding.get('issue_title')}"),
                "to": to_addresses or raw_result.get("to", []),
                "cc": cc_addresses,
                "body": raw_result.get("body", ""),
                "data_sources": data_sources
            },
            "editable": True,
            "copy_to_clipboard": True
        }
    except Exception as e:
        return {
            "email_draft": {
                "subject": f"Regarding: {agent_finding.get('issue_title', 'City Issue')}",
                "to": to_addresses,
                "cc": cc_addresses,
                "body": f"Dear City Official,\n\nI am writing as a resident of San Francisco regarding {agent_finding.get('issue_title', 'a city issue')}.\n\n{agent_finding.get('summary', '')}\n\nI request {desired_outcome or 'action on this matter'}.\n\nSincerely,\n{citizen_name or 'A concerned resident'}",
                "data_sources": []
            },
            "editable": True,
            "copy_to_clipboard": True,
            "error": str(e)
        }
        }


async def send_email(recipient_email: str, subject: str, body: str) -> dict:
    """Send an email using Composio's Gmail integration."""
    api_key = os.getenv("COMPOSIO_API_KEY") or COMPOSIO_API_KEY
    if not api_key:
        return {"success": False, "error": "COMPOSIO_API_KEY not found."}

    try:
        composio = Composio(api_key=api_key, provider=LangchainProvider())
        
        # Use asyncio.to_thread to run the synchronous Composio call in a separate thread
        result = await asyncio.to_thread(
            lambda: composio.execute(
                slug="GMAIL_SEND_EMAIL",
                arguments={
                    "recipient_email": recipient_email,
                    "subject": subject,
                    "body": body
                },
                user_id="default"
            )
        )
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
