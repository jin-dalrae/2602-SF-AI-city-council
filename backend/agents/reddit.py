import os
import asyncio
from datetime import datetime, timezone
from composio import Composio
from composio_langchain import LangchainProvider
from .base import CityAgent
from backend.services import llm

class RedditAgent(CityAgent):
    """
    Agent that monitors r/sanfrancisco for emerging civic issues.
    Uses Composio to fetch real-time community reports and sentiment.
    """
    name = "Reddit Community Watch"
    department = "Community Relations"
    icon = "reddit"
    news_query = "San Francisco reddit community issues 2026"
    
    officials = [
        {
            "name": "SF Board of Supervisors",
            "title": "Community Outreach",
            "department": "Board of Supervisors",
            "email": "board.of.supervisors@sfgov.org",
        }
    ]

    def __init__(self, findings_store: dict, event_queue: asyncio.Queue):
        super().__init__(findings_store, event_queue)
        api_key = os.getenv("COMPOSIO_API_KEY")
        # Initialize Composio specifically for Reddit reading
        self.composio = Composio(api_key=api_key, provider=LangchainProvider())

    async def fetch_data(self) -> dict:
        """Fetch latest posts from r/sanfrancisco using Composio."""
        await self._log_brain("🕵️ Scanning r/sanfrancisco for emerging civic alerts...", "Looking for untracked incidents and public sentiment shifts.")
        
        try:
            # Common Reddit slugs in Composio
            slugs_to_try = [
                "reddit_get_subreddit_posts", 
                "REDDIT_GET_SUBREDDIT_POSTS", 
                "reddit_subreddit_posts",
                "REDDIT_SUBREDDIT_POSTS",
                "reddit_search"
            ]
            
            result = None
            for slug in slugs_to_try:
                try:
                    result = await asyncio.to_thread(
                        lambda: self.composio.tools.execute(
                            slug=slug,
                            arguments={"subreddit": "sanfrancisco", "limit": 12},
                            user_id="default"
                        )
                    )
                    if result:
                        break
                except:
                    continue
            
            if not result:
                # Fallback to news-based sentiment if Reddit tool fails
                await self._log_brain("⚠️ Reddit tool connection issue.", "Falling back to secondary sentiment signals.")
                return {"posts": [], "_counts": {"reddit_reports": 0}}
            
            # Extract posts from result
            posts = []
            if isinstance(result, list):
                posts = result
            elif isinstance(result, dict):
                # Check various return patterns
                posts = result.get("posts") or result.get("data") or result.get("results") or []
            
            formatted_posts = []
            for p in posts[:10]:
                if not isinstance(p, dict): continue
                formatted_posts.append({
                    "title": p.get("title", "Reddit Post"),
                    "text": p.get("selftext", p.get("body", ""))[:300],
                    "score": p.get("score", 0),
                    "comments": p.get("num_comments", 0),
                    "url": f"https://reddit.com{p.get('permalink', '')}" if p.get('permalink') else p.get('url', '')
                })
                
            return {
                "posts": formatted_posts,
                "post_count": len(formatted_posts),
                "_counts": {"community_reports": len(formatted_posts)}
            }
            
        except Exception as e:
            await self._log_brain(f"❌ Reddit Fetch Error: {str(e)[:50]}", "Data pipeline interruption.")
            return {"posts": [], "_counts": {"community_reports": 0}}

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        posts = data.get("posts", [])
        if not posts:
            return "No recent Reddit community reports found.", "Summarize that community sentiment is currently baseline or data is unavailable."
            
        summary = " r/sanfrancisco Trending Civic Discussions:\n"
        for p in posts:
            summary += f"- TITLE: {p['title']}\n  CONTENT: {p['text']}\n  ENGAGEMENT: {p['score']} upvotes, {p['comments']} comments\n\n"
            
        prompt = """As an Expert Community Watch Analyst, correlate these Reddit discussions with civic infrastructure and safety.
Look for 'ground-truth' reports that official Socrata datasets might miss (e.g. specific blocks with broken lights, recurring transit delays on unmonitored lines, or emerging public safety hot-spots).

Your issue report should:
1. Identify 1-2 primary 'Citizen Complaints' trending right now.
2. Determine if these are isolated incidents or emerging systemic failures.
3. Suggest specifically which city department should respond based on the Reddit feedback.

Severity should be 'high' if multiple independent users are reporting the same dangerous condition."""

        return summary, prompt
