from .base import CityAgent


class PublicWorksAgent(CityAgent):
    name = "311 Service Requests"
    department = "Public Works"
    icon = "wrench"
    news_query = "San Francisco 311 public works infrastructure maintenance 2025"
    datasets = {"requests": "vw6y-z8j6"}
    officials = [
        {"name": "Director of Public Works", "title": "SF Public Works Director", "email": "dpw@sfgov.org"},
    ]

    async def fetch_data(self) -> dict:
        # Open cases by service_name
        by_category = await self.socrata.fetch_recent(
            self.datasets["requests"],
            date_field="requested_datetime",
            days=90,
            select="service_name, count(*) as cnt",
            group="service_name",
            order="cnt DESC",
            limit=15,
        )

        # Status breakdown
        by_status = await self.socrata.fetch_recent(
            self.datasets["requests"],
            date_field="requested_datetime",
            days=90,
            select="status_description, count(*) as cnt",
            group="status_description",
            order="cnt DESC",
            limit=10,
        )

        # Backlog: still open cases
        backlog = await self.socrata.fetch(
            self.datasets["requests"],
            where="status_description = 'Open'",
            select="service_name, count(*) as cnt",
            group="service_name",
            order="cnt DESC",
            limit=10,
        )

        total = sum(int(r.get("cnt", 0)) for r in by_category)
        open_count = sum(
            int(r.get("cnt", 0)) for r in by_status if r.get("status_description") == "Open"
        )

        return {
            "total_requests": total,
            "open_count": open_count,
            "by_category": [
                {"category": r.get("service_name", "Unknown"), "count": int(r.get("cnt", 0))}
                for r in by_category[:10]
            ],
            "by_status": [
                {"status": r.get("status_description", "Unknown"), "count": int(r.get("cnt", 0))}
                for r in by_status
            ],
            "backlog": [
                {"category": r.get("service_name", "Unknown"), "count": int(r.get("cnt", 0))}
                for r in backlog[:5]
            ],
            "_counts": {"total_90d": total, "currently_open": open_count},
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        summary = f"""SF 311 Service Requests (Last 90 Days):
Total requests: {data['total_requests']}
Currently open: {data['open_count']}

Top categories:
{chr(10).join(f"- {c['category']}: {c['count']}" for c in data['by_category'])}

Status breakdown:
{chr(10).join(f"- {s['status']}: {s['count']}" for s in data['by_status'])}

Largest backlogs (open cases):
{chr(10).join(f"- {b['category']}: {b['count']} open" for b in data['backlog'])}"""

        prompt = """Analyze these 311 service request patterns for a civic advocacy NGO.
Identify categories with growing backlogs, slow response times, or systemic neglect.
Recommend specific policy actions to improve city services."""

        return summary, prompt
