import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from backend.services.socrata import SocrataClient
from backend.services import llm, you_api


class CityAgent(ABC):
    name: str = ""
    department: str = ""
    icon: str = ""
    news_query: str = ""  # Each agent sets a You.com search query for news
    datasets: dict[str, str] = {}  # {label: dataset_id}
    officials: list[dict] = []     # [{name, title, email}]

    def __init__(self, findings_store: dict, event_queue: asyncio.Queue):
        self.socrata = SocrataClient()
        self.findings_store = findings_store
        self.event_queue = event_queue

    @abstractmethod
    async def fetch_data(self) -> dict:
        """Fetch and summarize raw data from Socrata."""
        ...

    @abstractmethod
    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        """Return (data_summary, analysis_prompt) for LLM."""
        ...

    async def fetch_news(self) -> list[str]:
        """Fetch recent news via You.com API relevant to this agent's domain."""
        if not self.news_query:
            return []
        raw = await you_api.search_context(self.news_query)
        if raw.startswith("Search error") or raw.startswith("You.com API"):
            return []
        return [line.strip("- ").strip() for line in raw.split("\n") if line.strip()]

    async def analyze(self, data: dict, news: list[str]) -> dict:
        data_summary, prompt = self.build_analysis_prompt(data)
        if news:
            data_summary += "\n\nRecent News & Context:\n" + "\n".join(f"- {n}" for n in news)
            prompt += "\nAlso consider the recent news context when forming your analysis and recommendations."
        finding = await llm.analyze_data(self.name, data_summary, prompt)
        finding["news_context"] = news
        return finding

    async def check_collaborations(self, all_findings: dict) -> dict | None:
        """Check for cross-agent topic overlap using keywords and news context."""
        my_finding = all_findings.get(self.name)
        if not my_finding:
            return None

        # Build keyword set from title, summary, and news
        my_keywords = set()
        text_sources = [
            my_finding.get("issue_title", ""),
            my_finding.get("summary", ""),
        ]
        for n in my_finding.get("news_context", []):
            text_sources.append(n)
        full_text = " ".join(text_sources).lower()
        for word in full_text.split():
            cleaned = word.strip(".,!?;:'\"()[]")
            if len(cleaned) > 4:
                my_keywords.add(cleaned)

        for other_name, other_finding in all_findings.items():
            if other_name == self.name or other_name.startswith("Collaboration:"):
                continue
            other_text = " ".join([
                other_finding.get("issue_title", ""),
                other_finding.get("summary", ""),
                " ".join(other_finding.get("news_context", [])),
            ]).lower()
            overlap = sum(1 for kw in my_keywords if kw in other_text)
            if overlap >= 2:
                collab = await llm.generate_collaboration(
                    self.name, other_name, my_finding, other_finding
                )
                return {
                    "agents": [self.name, other_name],
                    "finding": collab,
                }
        return None

    async def run_once(self):
        try:
            # Fetch data and news in parallel
            data, news = await asyncio.gather(
                self.fetch_data(),
                self.fetch_news(),
            )
            finding = await self.analyze(data, news)
            output = {
                "agent_name": self.name,
                "department": self.department,
                "icon": self.icon,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "officials": self.officials,
                "raw_counts": data.get("_counts", {}),
                **finding,
            }
            self.findings_store[self.name] = output
            await self.event_queue.put({"type": "finding", "data": output})

            # Check collaborations after updating own findings
            collab = await self.check_collaborations(self.findings_store)
            if collab:
                collab_key = f"Collaboration: {collab['agents'][0]} + {collab['agents'][1]}"
                collab_output = {
                    "agent_name": collab_key,
                    "department": "Cross-Agency",
                    "icon": "link",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "officials": [],
                    "raw_counts": {},
                    "news_context": [],
                    **collab["finding"],
                }
                self.findings_store[collab_key] = collab_output
                await self.event_queue.put({"type": "finding", "data": collab_output})
        except Exception as e:
            error_output = {
                "agent_name": self.name,
                "department": self.department,
                "icon": self.icon,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "officials": self.officials,
                "raw_counts": {},
                "issue_title": f"{self.name} - Data Collection Error",
                "severity": "low",
                "summary": f"Error during data collection: {str(e)[:200]}",
                "key_metrics": [],
                "evidence": [],
                "solution": "Will retry on next cycle.",
                "affected_neighborhoods": [],
                "news_context": [],
            }
            self.findings_store[self.name] = error_output
            await self.event_queue.put({"type": "finding", "data": error_output})

    async def run_loop(self, interval: int = 60):
        while True:
            await self.run_once()
            await asyncio.sleep(interval)
