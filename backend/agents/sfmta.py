from .base import CityAgent


class SFMTAAgent(CityAgent):
    name = "SFMTA Transit"
    department = "Municipal Transportation Agency"
    icon = "bus"
    news_query = "San Francisco Muni transit SFMTA service performance equity 2025"
    datasets = {"citations": "8pxu-u28x"}
    officials = [
        {"name": "SFMTA Director", "title": "Director of Transportation", "email": "mtadirector@sfmta.com"},
    ]

    async def fetch_data(self) -> dict:
        # Fare citation data - total count
        citations = await self.socrata.fetch(
            self.datasets["citations"],
            select="count(*) as total_citations",
            limit=1,
        )

        # Recent citations breakdown by violation description
        recent = await self.socrata.fetch(
            self.datasets["citations"],
            select="violation_desc, count(*) as cnt",
            group="violation_desc",
            order="cnt DESC",
            limit=10,
        )

        total = int(citations[0].get("total_citations", 0)) if citations else 0

        return {
            "total_citations": total,
            "citation_types": [
                {"violation": r.get("violation_desc", "Unknown"), "count": int(r.get("cnt", 0))}
                for r in recent
            ],
            "_counts": {"total_citations": total},
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        summary = f"""SFMTA Transit Data:
Total fare citations: {data['total_citations']}

Citation types:
{chr(10).join(f"- {c['violation']}: {c['count']}" for c in data['citation_types'])}"""

        prompt = """Analyze transit fare citation data and current service context for an NGO
focused on equitable transportation access.
Consider how fare enforcement policies affect low-income riders.
Recommend policy actions to improve transit equity and service reliability."""

        return summary, prompt
