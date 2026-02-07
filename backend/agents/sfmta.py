from .base import CityAgent


class SFMTAAgent(CityAgent):
    name = "Transit Authority"
    department = "Municipal Transportation Agency"
    icon = "bus"
    news_query = "San Francisco Muni transit SFMTA service performance equity 2025"
    datasets = {"citations": "8pxu-u28x"}
    officials = [
        {"name": "SFMTA Director", "title": "Director of Transportation", "email": "mtadirector@sfmta.com"},
    ]

    async def fetch_data(self) -> dict:
        # Monthly trends
        trends = await self.socrata.fetch_trends(
            self.datasets["citations"],
            date_field="citation_date",
            days=180,
            period="month"
        )

        # Recent breakdown
        recent = await self.socrata.fetch_recent(
            self.datasets["citations"],
            date_field="citation_date",
            days=30,
            select="violation_desc, count(*) as cnt",
            group="violation_desc",
            order="cnt DESC",
            limit=10,
        )

        total_30d = sum(int(r.get("cnt", 0)) for r in recent)

        return {
            "total_30d": total_30d,
            "monthly_trends": [
                {"month": r.get("period", "").split("T")[0][:7], "count": int(r.get("cnt", 0))}
                for r in trends
            ],
            "citation_types": [
                {"violation": r.get("violation_desc", "Unknown"), "count": int(r.get("cnt", 0))}
                for r in recent
            ],
            "_counts": {"last_30d_citations": total_30d},
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        summary = f"""SFMTA Transit Citation Analysis:

Monthly Citation Trends (Last 6 Months):
{chr(10).join(f"- {t['month']}: {t['count']} citations" for t in data['monthly_trends'])}

Recent 30-Day Snapshot:
Total citations: {data['total_30d']}

Violation Categories (Last 30 Days):
{chr(10).join(f"- {c['violation']}: {c['count']}" for c in data['citation_types'])}"""

        prompt = """As an Expert Data Analyst, analyze the trajectory of transit enforcement.
Identify if citations are increasing month-over-month.
Consider the impact of these enforcement trends on transit equity and low-income riders.
Recommend policy changes based on the observed data patterns."""

        return summary, prompt
