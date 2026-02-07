from .base import CityAgent


class PublicWorksAgent(CityAgent):
    name = "Infrastructure Foreman"
    department = "Public Works"
    icon = "wrench"
    news_query = "San Francisco 311 public works infrastructure maintenance 2025"
    datasets = {"requests": "vw6y-z8j6"}
    officials = [
        {"name": "Director of Public Works", "title": "SF Public Works Director", "email": "dpw@sfgov.org"},
    ]

    async def fetch_data(self) -> dict:
        # Trends by month (last 180 days)
        trends = await self.socrata.fetch_trends(
            self.datasets["requests"],
            date_field="requested_datetime",
            days=180,
            period="month"
        )

        # Recent breakdown (last 30 days - sharper focus)
        by_category = await self.socrata.fetch_recent(
            self.datasets["requests"],
            date_field="requested_datetime",
            days=30,
            select="service_name, count(*) as cnt",
            group="service_name",
            order="cnt DESC",
            limit=10,
        )

        # Status breakdown
        by_status = await self.socrata.fetch_recent(
            self.datasets["requests"],
            date_field="requested_datetime",
            days=30,
            select="status_description, count(*) as cnt",
            group="status_description",
            limit=5,
        )

        # Backlog: still open cases
        backlog = await self.socrata.fetch(
            self.datasets["requests"],
            where="status_description = 'Open'",
            select="service_name, count(*) as cnt",
            group="service_name",
            order="cnt DESC",
            limit=5,
        )

        total_30d = sum(int(r.get("cnt", 0)) for r in by_category)
        open_count = sum(
            int(r.get("cnt", 0)) for r in by_status if r.get("status_description") == "Open"
        )

        return {
            "total_30d": total_30d,
            "open_count": open_count,
            "monthly_trends": [
                {"month": r.get("period", "").split("T")[0][:7], "count": int(r.get("cnt", 0))}
                for r in trends
            ],
            "by_category": [
                {"category": r.get("service_name", "Unknown"), "count": int(r.get("cnt", 0))}
                for r in by_category
            ],
            "backlog": [
                {"category": r.get("service_name", "Unknown"), "count": int(r.get("cnt", 0))}
                for r in backlog
            ],
            "_counts": {"last_30d": total_30d, "open": open_count},
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        summary = f"""SF 311 Service Requests Analysis:

Monthly Volume Trends (Last 6 Months):
{chr(10).join(f"- {t['month']}: {t['count']} requests" for t in data['monthly_trends'])}

Recent 30-Day Snapshot:
Total requests: {data['total_30d']}
Currently open: {data['open_count']}

Top request categories (Last 30 Days):
{chr(10).join(f"- {c['category']}: {c['count']}" for c in data['by_category'])}

Current Backlogs (Open cases):
{chr(10).join(f"- {b['category']}: {b['count']} open" for b in data['backlog'])}"""

        prompt = """As an Expert Data Analyst, identify significant shifts in city service demand.
Look at the Monthly Volume Trends: are requests surfacing faster than they are being closed?
Identify specific categories (like Potholes or Graffiti) where the backlog is disproportionately high compared to monthly volume.
Provide a trend-based analysis of department performance."""

        return summary, prompt
