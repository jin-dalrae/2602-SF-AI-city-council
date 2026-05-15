import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from backend import deps
from backend.services import llm, you_api, storage, composio_tools



class CityAgent(ABC):
    name: str = ""
    department: str = ""
    icon: str = ""
    news_query: str = ""  # Each agent sets a You.com search query for news
    datasets: dict[str, str] = {}  # {label: dataset_id}
    officials: list[dict] = []     # [{name, title, email}]
    def __init__(self, findings_store: dict, event_queue: asyncio.Queue):
        self.socrata = deps.socrata()
        self.findings_store = findings_store
        self.event_queue = event_queue
        self.brain_log: list[dict] = []
        # Load traits if they exist in store (persistence), otherwise start fresh
        stored = self.findings_store.get(f"_traits_{self.name}")
        self.traits: list[str] = stored if stored else ["Expert Data Analyst"]

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

        # --- Current Issues Context ---
        current_issues = [v for k, v in self.findings_store.items() if k.startswith(self.name) and not k.startswith("_")]
        if current_issues:
            issue_list = "\n".join([f"- {i.get('issue_title')} (Severity: {i.get('severity')})" for i in current_issues])
            prompt += f"\n\nCURRENT ACTIVE ISSUES BY YOU:\n{issue_list}\nIf this new data relates to one of these, reuse the exact title to update it."
        # ------------------------------
        
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

    async def _log_brain(self, message: str, thought: str = "", icon: str = None):
        """Send a technical update to the status brain feed."""
        log = {
            "agent_name": self.name,
            "message": message,
            "thought": thought,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "icon": icon or self.icon
        }
        self.brain_log.append(log)
        if hasattr(self, "event_queue") and self.event_queue:
            await self.event_queue.put({"type": "brain", "data": log})

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
        STOP_WORDS = {"about", "across", "after", "again", "against", "almost", "along", "already", "also", "although", "always", "among", "another", "anyhow", "anyone", "anything", "anywhere", "around", "became", "because", "become", "becomes", "becoming", "before", "behind", "being", "below", "beside", "besides", "between", "beyond", "cannot", "could", "couldn", "didnt", "doesnt", "doing", "don't", "done", "during", "either", "else", "elsewhere", "enough", "even", "ever", "every", "everyone", "everything", "everywhere", "except", "further", "hadnt", "hasnt", "have", "havent", "hence", "here", "hereafter", "hereby", "herein", "hereupon", "hers", "herself", "himself", "howbeit", "however", "indeed", "inside", "instead", "into", "itself", "last", "latter", "least", "less", "many", "maybe", "meanwhile", "might", "more", "moreover", "most", "mostly", "much", "must", "myself", "namely", "neither", "never", "nevertheless", "next", "nobody", "none", "noone", "nothing", "nowhere", "often", "only", "onto", "other", "others", "otherwise", "ours", "ourselves", "perhaps", "please", "rather", "same", "seem", "seemed", "seeming", "seems", "several", "since", "some", "somehow", "someone", "something", "sometime", "sometimes", "somewhere", "still", "such", "than", "that", "their", "them", "themselves", "then", "thence", "there", "thereafter", "thereby", "therefore", "therein", "thereupon", "these", "they", "this", "those", "though", "through", "throughout", "thru", "thus", "together", "under", "until", "upon", "very", "wasnt", "were", "werent", "what", "whatever", "when", "whence", "whenever", "where", "whereafter", "whereas", "whereby", "wherein", "whereupon", "wherever", "whether", "which", "while", "whither", "whoever", "whole", "whom", "whose", "why", "will", "within", "without", "would", "yours", "yourself", "yourselves"}
        for word in full_text.split():
            cleaned = word.strip(".,!?;:'\"()[]").lower()
            if len(cleaned) > 4 and cleaned not in STOP_WORDS:
                my_keywords.add(cleaned)

        for other_name, other_finding in all_findings.items():
            if other_name == self.name or other_name.startswith(f"{self.name}:") or other_name.startswith("Collaboration:") or other_name.startswith("_"):
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
            action_result = await composio_tools.trigger_civic_action(self.name, finding)
            if action_result.get("status") == "success":
                await self._log_brain(
                    f"🚀 Created Civic Ticket on GitHub for: {finding.get('issue_title')[:50]}...",
                    "This severity warrants automated advocacy tracking.",
                    icon="🚀"
                )
            # ------------------------------------

            # --- Brain Evolution Step (trait-only; source rewrites removed) ---
            evolution = await llm.evolve_brain(self.name, self.traits, finding)
            if evolution.get("new_trait") and evolution["new_trait"] not in self.traits:
                new_trait = evolution["new_trait"]
                self.traits.append(new_trait)
                self.findings_store[f"_traits_{self.name}"] = self.traits
                await self._log_brain(f"🧬 Evolved new capability: {new_trait}", evolution.get("evolved_thought", "Improving analytical depth."), icon="🧬")

            # --- Issue Merging/Updating Logic ---
            issue_title = finding.get("issue_title", "General Update")
            # Use agent:title as the unique key (consistent with frontend logic)
            storage_key = f"{self.name}:{issue_title}"
            
            existing = self.findings_store.get(storage_key) or self.findings_store.get(self.name)
            
            # Initialize or merge status updates
            updates = []
            if existing and isinstance(existing, dict):
                updates = existing.get("status_updates", [])
            
            new_update = finding.get("status_updates", [])
            if new_update:
                updates.extend(new_update)
            
            # Keep only last 5 updates to prevent bloat
            updates = updates[-5:]
            
            output = {
                "agent_name": self.name,
                "department": self.department,
                "icon": self.icon,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "officials": self.officials,
                "raw_counts": data.get("_counts", {}),
                "traits": self.traits,
                **finding,
                "status_updates": updates
            }
            
            self.findings_store[storage_key] = output
            await self.event_queue.put({"type": "finding", "data": output})
            await storage.append_to_history(output)

            # --- Save to Episodic Memory ---
            mem_summary = f"{finding.get('issue_title')}: {finding.get('summary')}"
            mem_emb = await llm.get_embedding(mem_summary)
            await storage.save_memory(self.name, mem_summary, mem_emb)
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
                await storage.append_to_history(collab_output)

        except Exception as e:
            error_title = f"{self.name} - Data Collection Error"
            error_output = {
                "agent_name": self.name,
                "department": self.department,
                "icon": self.icon,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "officials": self.officials,
                "raw_counts": {},
                "issue_title": error_title,
                "severity": "low",
                "summary": f"Error during data collection: {str(e)[:200]}",
                "key_metrics": [],
                "evidence": [],
                "solution": "Will retry on next cycle.",
                "affected_neighborhoods": [],
                "news_context": [],
            }
            self.findings_store[f"{self.name}:{error_title}"] = error_output
            await self.event_queue.put({"type": "finding", "data": error_output})

    async def run_loop(self, interval: int = 60):
        while True:
            await self.run_once()
            await asyncio.sleep(interval)
