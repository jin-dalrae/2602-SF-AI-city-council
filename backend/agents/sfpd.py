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
        # Weekly Trends (Last 90 days)
        trends = await self.socrata.fetch_trends(
            self.datasets["incidents"],
            date_field="incident_date",
            days=90,
            period="week"
        )

        # Recent Snapshot (Last 30 days)
        records = await self.socrata.fetch_recent(
            self.datasets["incidents"],
            date_field="incident_date",
            days=30,
            select="incident_category, count(*) as cnt",
            group="incident_category",
            order="cnt DESC",
            limit=10,
        )

        # District breakdown (Last 30 days)
        districts = await self.socrata.fetch_recent(
            self.datasets["incidents"],
            date_field="incident_date",
            days=30,
            select="police_district, count(*) as cnt",
            group="police_district",
            order="cnt DESC",
            limit=10,
        )

        total_30d = sum(int(r.get("cnt", 0)) for r in records)

        return {
            "total_30d": total_30d,
            "weekly_trends": [
                {"week_start": r.get("period", "").split("T")[0], "count": int(r.get("cnt", 0))}
                for r in trends
            ],
            "top_categories": [
                {"category": r["incident_category"], "count": int(r["cnt"])}
                for r in records
            ],
            "districts": [
                {"district": d.get("police_district", "Unknown"), "count": int(d.get("cnt", 0))}
                for d in districts
            ],
            "_counts": {"last_30d_incidents": total_30d},
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        summary = f"""San Francisco Incident Analysis:

Weekly Incident Trends (Last 12 Weeks):
{chr(10).join(f"- Week starting {t['week_start']}: {t['count']} incidents" for t in data['weekly_trends'])}

Recent 30-Day Snapshot:
Total incidents: {data['total_30d']}

Top Categories (Last 30 Days):
{chr(10).join(f"- {c['category']}: {c['count']}" for c in data['top_categories'])}

Incidents by District (Last 30 Days):
{chr(10).join(f"- {d['district']}: {d['count']}" for d in data['districts'])}"""

        prompt = """As an Expert Data Analyst, identify significant shifts in public safety.
Look at the Weekly Incident Trends: are certain weeks spiking unusually?
Cross-reference the Top Categories with the Districts: which areas are seeing specific types of crime increase?
Identify trends that require immediate community intervention or policy adjustment."""

        return summary, prompt
