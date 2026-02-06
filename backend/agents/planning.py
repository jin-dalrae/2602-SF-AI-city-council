from .base import CityAgent


class PlanningAgent(CityAgent):
    name = "Building Permits"
    department = "Planning Department"
    icon = "building"
    news_query = "San Francisco housing development building permits zoning 2025"
    datasets = {"permits": "i98e-djp9"}
    officials = [
        {"name": "Planning Director", "title": "SF Planning Director", "email": "planning@sfgov.org"},
    ]

    async def fetch_data(self) -> dict:
        # Recent permits by type definition
        by_type = await self.socrata.fetch_recent(
            self.datasets["permits"],
            date_field="filed_date",
            days=90,
            select="permit_type_definition, count(*) as cnt",
            group="permit_type_definition",
            order="cnt DESC",
            limit=15,
        )

        # Status breakdown
        by_status = await self.socrata.fetch_recent(
            self.datasets["permits"],
            date_field="filed_date",
            days=90,
            select="status, count(*) as cnt",
            group="status",
            order="cnt DESC",
            limit=10,
        )

        # Total count of permits
        count_data = await self.socrata.fetch_recent(
            self.datasets["permits"],
            date_field="filed_date",
            days=90,
            select="count(*) as total_permits",
            limit=1,
        )

        total_permits = int(count_data[0].get("total_permits", 0)) if count_data else 0
        total_cost = 0.0  # estimated_cost is text, skip aggregation

        return {
            "total_permits": total_permits,
            "total_estimated_cost": total_cost,
            "by_type": [
                {"type": r.get("permit_type_definition", "Unknown"), "count": int(r.get("cnt", 0))}
                for r in by_type[:10]
            ],
            "by_status": [
                {"status": r.get("status", "Unknown"), "count": int(r.get("cnt", 0))}
                for r in by_status
            ],
            "_counts": {
                "total_permits_90d": total_permits,
                "total_cost": f"${total_cost:,.0f}",
            },
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        summary = f"""SF Building Permits (Last 90 Days):
Total permits filed: {data['total_permits']}
Total estimated cost: ${data['total_estimated_cost']:,.0f}

Permits by type:
{chr(10).join(f"- {t['type']}: {t['count']}" for t in data['by_type'])}

Permits by status:
{chr(10).join(f"- {s['status']}: {s['count']}" for s in data['by_status'])}"""

        prompt = """As an Expert Data Analyst, analyze building permit data for a citizen oversight dashboard.
Identify trends in permit types, approval bottlenecks, and housing development patterns.
Recommend policy actions to improve housing affordability and community-focused development."""

        return summary, prompt
