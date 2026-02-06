"""
SF News Agent - Uses You.com API to aggregate real-time San Francisco news.

This agent doesn't fetch Socrata data. Instead, it queries You.com for the latest
SF civic news and provides insights that other agents can use for context.
"""

import asyncio
from datetime import datetime, timezone
from backend.services import llm, you_api, storage



class SFNewsAgent:
    """
    A specialized agent that aggregates SF news from You.com API.
    Unlike other CityAgents, this one doesn't fetch Socrata data.
    It provides a news feed that other agents reference for context.
    """

    name = "SF News Agent"
    department = "News & Media"
    icon = "📰"
    
    # News topics to search
    NEWS_QUERIES = [
        "San Francisco city government news today",
        "San Francisco budget housing transit crime latest",
        "San Francisco mayor board of supervisors decisions 2026",
        "San Francisco infrastructure public works updates",
        "San Francisco community safety SFPD news",
    ]
    
    # Officials for press/media inquiries
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

    def __init__(self, findings_store: dict, event_queue: asyncio.Queue):
        self.findings_store = findings_store
        self.event_queue = event_queue

    async def fetch_news(self) -> list[dict]:
        """
        Fetch news from You.com API using multiple queries to get comprehensive coverage.
        Returns a list of news items with their source topic.
        """
        all_news = []
        
        for query in self.NEWS_QUERIES:
            try:
                raw = await you_api.search_context(query)
                if raw.startswith("Search error") or raw.startswith("You.com API"):
                    continue
                
                # Parse bullet points from response
                lines = [
                    line.strip("- ").strip()
                    for line in raw.split("\n")
                    if line.strip() and not line.startswith("Search error")
                ]
                
                for line in lines:
                    if len(line) > 20:  # Filter out very short items
                        all_news.append({
                            "topic": query.split(" ")[2] if len(query.split(" ")) > 2 else "general",
                            "headline": line,
                        })
            except Exception as e:
                print(f"[SF News Agent] Error fetching news for '{query}': {e}")
                continue
        
        # Deduplicate based on headline similarity (simple approach)
        seen = set()
        unique_news = []
        for item in all_news:
            # Use first 50 chars as a simple dedup key
            key = item["headline"][:50].lower()
            if key not in seen:
                seen.add(key)
                unique_news.append(item)
        
        return unique_news[:15]  # Limit to top 15 items

    async def analyze_news(self, news_items: list[dict]) -> dict:
        """
        Use LLM to analyze the collected news and generate insights.
        """
        if not news_items:
            return {
                "issue_title": "No Recent News Available",
                "severity": "low",
                "summary": "Unable to fetch recent San Francisco news at this time.",
                "key_metrics": [],
                "evidence": [],
                "solution": "News aggregation will resume on the next cycle.",
                "affected_neighborhoods": [],
                "trending_topics": [],
            }

        # Build news summary for LLM
        news_text = "\n".join([f"- {item['headline']}" for item in news_items])
        
        data_summary = f"""
Recent San Francisco News Headlines (via You.com):
{news_text}
"""
        
        analysis_prompt = """
Analyze these recent San Francisco news headlines and provide:

1. **Issue Title**: A headline summarizing the most significant civic issue emerging from the news
2. **Severity**: Rate as "urgent", "moderate", or "low" based on impact to SF residents
3. **Summary**: 2-3 sentences synthesizing the key themes and developments
4. **Key Metrics**: List any numbers, percentages, or quantifiable data mentioned
5. **Trending Topics**: List 3-5 topics that appear frequently (e.g., "housing", "transit", "public safety")
6. **Relevant Neighborhoods**: Any specific SF neighborhoods mentioned
7. **Recommended Actions**: What should NGOs or citizens focus on based on this news?

Focus on civic issues like housing, transportation, public safety, budget, and infrastructure.
Identify connections between news items that reveal larger patterns.
"""
        
        finding = await llm.analyze_data(self.name, data_summary, analysis_prompt)
        
        # Add trending topics extraction
        topics = set()
        topic_keywords = {
            "housing": ["housing", "rent", "eviction", "affordable", "homeless"],
            "transit": ["muni", "bart", "transit", "transportation", "bus", "sfmta"],
            "public safety": ["crime", "police", "safety", "sfpd", "shooting"],
            "budget": ["budget", "funding", "tax", "spending", "fiscal"],
            "infrastructure": ["construction", "repair", "potholes", "streets", "infrastructure"],
            "environment": ["climate", "clean", "pollution", "parks", "environmental"],
        }
        
        all_text = " ".join([item["headline"].lower() for item in news_items])
        for topic, keywords in topic_keywords.items():
            if any(kw in all_text for kw in keywords):
                topics.add(topic)
        
        finding["trending_topics"] = list(topics)
        finding["raw_headlines"] = [item["headline"] for item in news_items[:10]]
        
        return finding

    async def run_once(self):
        """Execute one cycle of news aggregation and analysis."""
        try:
            print(f"[{self.name}] Fetching news from You.com...")
            news_items = await self.fetch_news()
            print(f"[{self.name}] Found {len(news_items)} news items")
            
            finding = await self.analyze_news(news_items)
            
            output = {
                "agent_name": self.name,
                "department": self.department,
                "icon": self.icon,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "officials": self.officials,
                "raw_counts": {"news_items": len(news_items)},
                "news_context": [item["headline"] for item in news_items],
                **finding,
            }
            
            self.findings_store[self.name] = output
            await self.event_queue.put({"type": "finding", "data": output})
            storage.append_to_history(output)  # Save to history
            
            # Also store news items for other agents to reference
            self.findings_store["_news_headlines"] = news_items

            
        except Exception as e:
            print(f"[{self.name}] Error: {e}")
            error_output = {
                "agent_name": self.name,
                "department": self.department,
                "icon": self.icon,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "officials": self.officials,
                "raw_counts": {},
                "issue_title": f"{self.name} - News Fetch Error",
                "severity": "low",
                "summary": f"Error during news aggregation: {str(e)[:200]}",
                "key_metrics": [],
                "evidence": [],
                "solution": "Will retry on next cycle.",
                "affected_neighborhoods": [],
                "trending_topics": [],
                "news_context": [],
            }
            self.findings_store[self.name] = error_output
            await self.event_queue.put({"type": "finding", "data": error_output})

    async def run_loop(self, interval: int = 90):
        """
        Run the news agent in continuous loop.
        Uses a slightly longer interval (90s) to avoid rate limiting.
        """
        while True:
            await self.run_once()
            await asyncio.sleep(interval)
