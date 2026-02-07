import os
import asyncio
from datetime import datetime, timezone
from composio import Composio
from composio_langchain import LangchainProvider
from .base import CityAgent
from backend.services import llm

class XAgent(CityAgent):
    """
    Agent that monitors X (Twitter) for SF tech scene trends, AI developments,
    and startup ecosystem shifts.
    """
    name = "SF Tech Scouter"
    department = "Technology & Innovation"
    icon = "x-logo"
    news_query = "San Francisco tech scene AI startups trends 2026"
    
    officials = [
        {
            "name": "Mayor's Office of Economic & Workforce Development",
            "title": "Director of Innovation",
            "department": "OEWD",
            "email": "oewd.innovation@sfgov.org",
        }
    ]

    def __init__(self, findings_store: dict, event_queue: asyncio.Queue):
        super().__init__(findings_store, event_queue)
        api_key = os.getenv("COMPOSIO_API_KEY")
        self.composio = Composio(api_key=api_key, provider=LangchainProvider())

    async def fetch_data(self) -> dict:
        """Fetch latest posts from X regarding SF tech scene."""
        await self._log_brain("🔍 Scouring X for SF Tech & AI ecosystem signals...", "Analyzing sentiment and emerging innovation patterns.")
        
        try:
            # Common Twitter/X slugs in Composio
            slugs_to_try = [
                "twitter_search", 
                "TWITTER_SEARCH", 
                "twitter_get_tweets",
                "x_search",
                "X_SEARCH"
            ]
            
            # Since X search often requires specific queries, we'll try a tech-focused one
            query = "San Francisco #AI #startups #tech"
            
            result = None
            for slug in slugs_to_try:
                try:
                    result = await asyncio.to_thread(
                        lambda: self.composio.tools.execute(
                            slug=slug,
                            arguments={"query": query, "limit": 10},
                            user_id="default"
                        )
                    )
                    if result:
                        break
                except:
                    continue
            
            if not result:
                await self._log_brain("⚠️ X tool connection issue.", "Falling back to news-based tech sentiment.")
                return {"tweets": [], "_counts": {"tech_signals": 0}}
            
            # Extract tweets from result
            tweets = []
            if isinstance(result, list):
                tweets = result
            elif isinstance(result, dict):
                tweets = result.get("tweets") or result.get("data") or result.get("results") or []
            
            formatted_tweets = []
            for t in tweets[:10]:
                if not isinstance(t, dict): continue
                formatted_tweets.append({
                    "text": t.get("text", t.get("full_text", ""))[:280],
                    "user": t.get("user", {}).get("screen_name", "user"),
                    "engagement": t.get("retweet_count", 0) + t.get("favorite_count", 0),
                    "timestamp": t.get("created_at", "")
                })
                
            return {
                "tweets": formatted_tweets,
                "tech_signal_count": len(formatted_tweets),
                "_counts": {"tech_ecosystem_signals": len(formatted_tweets)}
            }
            
        except Exception as e:
            await self._log_brain(f"❌ X Fetch error: {str(e)[:50]}", "Tech signal pipeline interrupted.")
            return {"tweets": [], "_counts": {"tech_ecosystem_signals": 0}}

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        tweets = data.get("tweets", [])
        if not tweets:
            return "No recent X tech trends found.", "Summarize current SF tech sentiment as stable but data-limited."
            
        summary = "X (Twitter) Trending SF Tech Discussions:\n"
        for t in tweets:
            summary += f"- USER: @{t['user']}\n  CONTENT: {t['text']}\n  ENGAGEMENT: {t['engagement']} signals\n\n"
            
        prompt = """As an Expert Tech Ecosystem Analyst, identify the 'Innovation Pulse' of San Francisco.
Look for:
1. Emerging AI trends or startup migrations.
2. Criticisms or praise regarding city tech policy (tax incentives, zoning for labs).
3. Sentiment regarding the 'Return to Office' vs remote work in the tech sector.

Identify 1 primary 'Council Opportunity' where the city can better support the tech ecosystem or mitigate negative externalities (like displacement).
"""

        return summary, prompt
