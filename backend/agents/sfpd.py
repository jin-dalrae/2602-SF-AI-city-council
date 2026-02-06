from .base import CityAgent


class SFPDAgent(CityAgent):
    name = "SFPD Crime Analysis"
    department = "Police Department"
    icon = "shield"
    news_query = "San Francisco crime safety public safety policy 2025"
    datasets = {"incidents": "wg3w-h783"}
    officials = [
        {"name": "Chief of Police", "title": "SFPD Chief", "email": "sfpdchief@sfgov.org"},
        {"name": "Police Commission", "title": "SF Police Commission", "email": "policecommission@sfgov.org"},
    ]

    async def fetch_data(self) -> dict:
        records = await self.socrata.fetch_recent(
            self.datasets["incidents"],
            date_field="incident_date",
            days=90,
            select="incident_category, count(*) as cnt",
            group="incident_category",
            order="cnt DESC",
            limit=20,
        )

        total = sum(int(r.get("cnt", 0)) for r in records)
        top_categories = [
            {"category": r["incident_category"], "count": int(r["cnt"])}
            for r in records[:10]
        ]

        # Also get district breakdown
        districts = await self.socrata.fetch_recent(
            self.datasets["incidents"],
            date_field="incident_date",
            days=90,
            select="police_district, count(*) as cnt",
            group="police_district",
            order="cnt DESC",
            limit=10,
        )

        return {
            "total_incidents": total,
            "top_categories": top_categories,
            "districts": [
                {"district": d.get("police_district", "Unknown"), "count": int(d.get("cnt", 0))}
                for d in districts
            ],
            "_counts": {"total_incidents_90d": total},
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        summary = f"""San Francisco Crime Data (Last 90 Days):
Total incidents: {data['total_incidents']}

Top incident categories:
{chr(10).join(f"- {c['category']}: {c['count']}" for c in data['top_categories'])}

Incidents by district:
{chr(10).join(f"- {d['district']}: {d['count']}" for d in data['districts'])}"""

        prompt = """Analyze this crime data for an NGO focused on community safety.
Identify the most concerning trends, any category spikes, and which neighborhoods need attention.
Recommend specific policy actions the NGO could advocate for."""

        return summary, prompt
