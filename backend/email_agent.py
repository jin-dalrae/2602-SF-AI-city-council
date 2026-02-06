import os
import json
from dotenv import load_dotenv
from backend.services import llm

load_dotenv()

COMPOSIO_API_KEY = "ak_zMx6z54f0h6_e1BApUnw"


async def draft_email(
    agent_finding: dict,
    ngo_name: str,
    desired_outcome: str,
    context: str,
    contact_person: str,
) -> dict:
    """Generate a professional email draft for city officials using Gemini."""
    officials = agent_finding.get("officials", [])
    to_addresses = [o.get("email", "") for o in officials if o.get("email")]
    to_names = [f"{o.get('name', '')} ({o.get('title', '')})" for o in officials]

    prompt = f"""Draft a professional email from an NGO to a city official.

NGO Name: {ngo_name}
Contact Person: {contact_person}
Recipients: {', '.join(to_names)}
Desired Outcome: {desired_outcome}
Additional Context: {context}

Issue Found by AI Analysis:
Title: {agent_finding.get('issue_title', 'N/A')}
Summary: {agent_finding.get('summary', 'N/A')}
Evidence: {json.dumps(agent_finding.get('evidence', []))}
Recommended Solution: {agent_finding.get('solution', 'N/A')}

Write a formal but compelling email that:
1. Introduces the NGO and its mission
2. References the specific data findings (minimum 2 data citations)
3. Proposes the desired outcome
4. Requests a meeting or response
5. Includes a 'Data Sources' footer section with relevant URLs from SF Open Data
6. Is respectful and professional

Return JSON with these fields:
- "subject": email subject line
- "body": full email body text (including the Data Sources footer)
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
                system_instruction="You are an expert NGO communications assistant. Always respond with valid JSON matching the requested structure.",
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
                "subject": raw_result.get("subject", f"Advocacy: {agent_finding.get('issue_title')}"),
                "to": to_addresses or raw_result.get("to", []),
                "cc": [],
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
                "cc": [],
                "body": f"Dear City Official,\n\nWe are writing on behalf of {ngo_name} regarding {agent_finding.get('issue_title', 'a city issue')}.\n\n{agent_finding.get('summary', '')}\n\nWe request {desired_outcome}.\n\nSincerely,\n{contact_person}\n{ngo_name}",
                "data_sources": []
            },
            "editable": True,
            "copy_to_clipboard": True,
            "error": str(e)
        }
