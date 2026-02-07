import asyncio
from datetime import datetime, timezone
from .base import CityAgent
from backend.services import llm, storage

class PolicyCoordinatorAgent(CityAgent):
    """
    A Meta-Agent that doesn't fetch raw city data. instead, it monitors all 
    other agents' findings to identify systemic patterns, merge related issues,
    and generate high-level "City Briefings".
    """
    name = "Policy Coordinator"
    department = "City Oversight"
    icon = "briefcase"
    news_query = "San Francisco multi-departmental city policy challenges 2026"
    
    officials = [
        {
            "name": "Carmen Chu",
            "title": "City Administrator",
            "department": "City Administrator's Office",
            "email": "city_administrator@sfgov.org",
        }
    ]

    async def fetch_data(self) -> dict:
        """Gather all current findings from the council table."""
        await self._log_brain("📑 Reviewing all active council findings...", "Identifying cross-departmental themes and systemic risks.")
        
        # Filter out self, news, and collaboration entries to get pure agent findings
        active_findings = []
        for key, finding in self.findings_store.items():
            if (not key.startswith("_") and 
                not key.startswith("Collaboration") and 
                key != self.name and
                isinstance(finding, dict)):
                active_findings.append(finding)
        
        return {
            "findings_count": len(active_findings),
            "findings": active_findings,
            "_counts": {"active_reports_monitored": len(active_findings)}
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        findings = data.get("findings", [])
        if not findings:
            return "No active findings currently on the council table.", "Summarize that the city is in a steady state with no emerging multi-departmental issues."
            
        summary = "--- ACTIVE COUNCIL FINDINGS ---\n\n"
        for f in findings:
            summary += f"AGENT: {f['agent_name']}\nISSUE: {f['issue_title']}\nSEVERITY: {f['severity']}\nSUMMARY: {f['summary']}\n\n"
            
        prompt = """As the Expert Policy Coordinator, perform a CRITICAL EVALUATION of all active findings.

1. **CRITICAL DEDUPLICATION**: If multiple agents are reporting different angles of the SAME core problem, you MUST merge them. 
2. **MERGE INTO FORMER THEMES**: Look at your 'CURRENT ACTIVE ISSUES' (provided below). If a new finding belongs to an existing theme you've already started, reuse that EXACT 'issue_title' to append new insights and metrics.
3. **ADVANCED SYNTHESIS**: Do not just repeat the agents. Connect the dots. Why is this happening? (e.g. 'The budget surplus in Public Works is failing to translate into safety because of a hiring bottleneck at SFMTA').
4. **POLISHED INSIGHT**: Produce a more sophisticated, "City Hall ready" insight that identifies the root cause.

Your goal is to reduce noise and increase signal. Merge similar signals into massive, evidence-rich master issues.
"""

        return summary, prompt

    async def run_once(self):
        # We need to ensure other agents have had a chance to work, 
        # but base.py run_once logic is fine. 
        # We just override it slightly if we wanted specific coordination logic.
        return await super().run_once()
