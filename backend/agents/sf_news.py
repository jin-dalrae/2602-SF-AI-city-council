"""SF News Agent — aggregates real-time San Francisco news via You.com.

Inherits CityAgent so it shares the same lifecycle (run_loop, traits,
memory, collaboration, error handling). The only customization is the data
source: instead of Socrata, it queries You.com across several topic-specific
queries and synthesizes a news digest.
"""

import asyncio
from datetime import datetime, timezone

from .base import CityAgent
from backend.services import you_api


# Topic-specific queries. Running multiple is the cheapest way to get
# diversified coverage without paying for a more sophisticated search API.
NEWS_QUERIES = [
    "San Francisco city government news today",
    "San Francisco budget housing transit crime latest",
    "San Francisco mayor board of supervisors decisions 2026",
    "San Francisco infrastructure public works updates",
    "San Francisco community safety SFPD news",
]

# Trending-topic keyword map; surfaces a quick scan signal alongside the LLM.
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "housing": ("housing", "rent", "eviction", "affordable", "homeless"),
    "transit": ("muni", "bart", "transit", "transportation", "bus", "sfmta"),
    "public safety": ("crime", "police", "safety", "sfpd", "shooting"),
    "budget": ("budget", "funding", "tax", "spending", "fiscal"),
    "infrastructure": ("construction", "repair", "potholes", "streets", "infrastructure"),
    "environment": ("climate", "clean", "pollution", "parks", "environmental"),
}


class SFNewsAgent(CityAgent):
    name = "Civic Correspondent"
    department = "News & Media"
    icon = "📰"
    news_query = ""  # Multi-query news fetch is handled in fetch_data.
    datasets: dict[str, str] = {}
    officials = [
        {
            "name": "Mayor's Press Office",
            "title": "Communications Director",
            "department": "Mayor's Office",
            "email": "mayorspressoffice@sfgov.org",
        },
        {
            "name": "SF Board of Supervisors",
            "title": "Clerk of the Board",
            "department": "Board of Supervisors",
            "email": "board.of.supervisors@sfgov.org",
        },
    ]

    async def _fetch_news_items(self) -> list[dict]:
        """Run the topic queries in parallel and dedupe results."""
        async def _one(q: str) -> list[dict]:
            raw = await you_api.search_context(q)
            if raw.startswith("Search error") or raw.startswith("You.com API"):
                return []
            items = []
            for line in raw.split("\n"):
                line = line.strip("- ").strip()
                if len(line) > 20:
                    items.append({"topic": q.split(" ")[2] if len(q.split(" ")) > 2 else "general",
                                  "headline": line})
            return items

        results = await asyncio.gather(*(_one(q) for q in NEWS_QUERIES), return_exceptions=True)

        seen: set[str] = set()
        unique: list[dict] = []
        for batch in results:
            if isinstance(batch, Exception) or not batch:
                continue
            for item in batch:
                key = item["headline"][:50].lower()
                if key in seen:
                    continue
                seen.add(key)
                unique.append(item)
                if len(unique) >= 15:
                    return unique
        return unique

    async def fetch_data(self) -> dict:
        news_items = await self._fetch_news_items()
        # Cache for sibling agents' contextual lookups.
        self.findings_store["_news_headlines"] = news_items
        return {
            "news_items": news_items,
            "_counts": {"news_items": len(news_items)},
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        items = data.get("news_items", [])
        if not items:
            return (
                "No recent SF news available.",
                "Summarize that the news pipeline is currently quiet.",
            )

        summary = "Recent San Francisco News Headlines (via You.com):\n" + "\n".join(
            f"- {item['headline']}" for item in items
        )
        prompt = """Analyze these recent San Francisco news headlines.

Produce a synthesized civic-news digest. Identify the most significant emerging
civic issue, the trending themes, and any specific SF neighborhoods involved.
Severity should reflect impact to SF residents on the canonical scale
(low / medium / high / critical)."""
        return summary, prompt

    async def analyze(self, data: dict, news: list[str]) -> dict:
        finding = await super().analyze(data, news)
        items = data.get("news_items", [])
        all_text = " ".join(i["headline"].lower() for i in items)
        finding["trending_topics"] = sorted(
            topic for topic, keywords in TOPIC_KEYWORDS.items()
            if any(kw in all_text for kw in keywords)
        )
        finding["raw_headlines"] = [i["headline"] for i in items[:10]]
        return finding
