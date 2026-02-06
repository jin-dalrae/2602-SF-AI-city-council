import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from backend.services.socrata import SocrataClient
from backend.services import llm, you_api, storage, actions



class CityAgent(ABC):
    name: str = ""
    department: str = ""
    icon: str = ""
    news_query: str = ""  # Each agent sets a You.com search query for news
    datasets: dict[str, str] = {}  # {label: dataset_id}
    officials: list[dict] = []     # [{name, title, email}]
    traits: list[str] = ["Expert Data Analyst"]
    brain_log: list[dict] = []     # [{"message", "thought", "timestamp"}]

    def __init__(self, findings_store: dict, event_queue: asyncio.Queue):
        self.socrata = SocrataClient()
        self.findings_store = findings_store
        self.event_queue = event_queue
        # Load traits if they exist in store (persistence)
        stored = self.findings_store.get(f"_traits_{self.name}")
        if stored:
            self.traits = stored

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
        
        # --- Memory Retrieval ---
        query_text = f"{self.name} {data_summary[:500]}"
        query_emb = await llm.get_embedding(query_text)
        memories = storage.search_memory(self.name, query_emb)
        # ------------------------

        if news:
            data_summary += "\n\nRecent News context provided to you:\n" + "\n".join(f"- {n}" for n in news)
            prompt += "\nReference the news context to reinforce your analysis."
        
        finding = await llm.analyze_data(self.name, data_summary, prompt, traits=self.traits, memories=memories)
        
        # --- World Verification Loop (You.com) ---
        # Agent proactively checks if its theory matches recent public discussion
        verification_query = f"San Francisco {finding.get('issue_title', '')} news 2026"
        verification_news = await you_api.search_context(verification_query)
        if verification_news and not (verification_news.startswith("Search error") or verification_news.startswith("You.com API")):
            finding["verified_context"] = verification_news
        # ----------------------------------------
        
        finding["recalled_memories"] = memories
        finding["news_context"] = news
        finding["traits"] = self.traits
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
            if other_name == self.name or other_name.startswith("Collaboration:") or other_name.startswith("_"):
                continue
            if not isinstance(other_finding, dict):
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
            
            # --- Active Action Loop (Composio) ---
            action_result = await actions.trigger_civic_action(self.name, finding)
            if action_result.get("status") == "success":
                action_msg = {
                    "agent_name": self.name,
                    "message": f"🚀 Created Civic Ticket on GitHub for: {finding.get('issue_title')[:50]}...",
                    "thought": "This severity warrants automated advocacy tracking.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "icon": "🚀"
                }
                self.brain_log.append(action_msg)
                await self.event_queue.put({"type": "brain", "data": action_msg})
            # ------------------------------------

            # --- Brain Evolution Step ---
            evolution = await llm.evolve_brain(self.name, self.traits, finding)
            if evolution.get("new_trait") and evolution["new_trait"] not in self.traits:
                self.traits.append(evolution["new_trait"])
                self.findings_store[f"_traits_{self.name}"] = self.traits

            learning = {
                "agent_name": self.name,
                "message": evolution.get("learning_message", "Analyzed latest dataset."),
                "thought": evolution.get("evolved_thought", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "icon": self.icon
            }
            self.brain_log.append(learning)
            await self.event_queue.put({"type": "brain", "data": learning})
            # ---------------------------

            output = {
                "agent_name": self.name,
                "department": self.department,
                "icon": self.icon,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "officials": self.officials,
                "raw_counts": data.get("_counts", {}),
                "traits": self.traits,
                **finding,
            }
            self.findings_store[self.name] = output
            await self.event_queue.put({"type": "finding", "data": output})
            storage.append_to_history(output)  # Save to history

            # --- Save to Episodic Memory ---
            mem_summary = f"{finding.get('issue_title')}: {finding.get('summary')}"
            mem_emb = await llm.get_embedding(mem_summary)
            storage.save_memory(self.name, mem_summary, mem_emb)
            # -------------------------------

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
                storage.append_to_history(collab_output)  # Save collaboration to history

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
