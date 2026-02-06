from .base import CityAgent


class BudgetAgent(CityAgent):
    name = "City Budget Analysis"
    department = "Office of the Controller"
    icon = "dollar-sign"
    news_query = "San Francisco city budget spending fiscal policy 2025"
    datasets = {"budget": "xdgd-c79v"}
    officials = [
        {"name": "City Controller", "title": "SF Controller", "email": "controller@sfgov.org"},
        {"name": "Budget Director", "title": "Budget & Legislative Analyst", "email": "budget.analyst@sfgov.org"},
    ]

    async def fetch_data(self) -> dict:
        # Spending by department for the most recent fiscal year
        spending = await self.socrata.fetch(
            self.datasets["budget"],
            where="revenue_or_spending = 'Spending'",
            select="department, sum(budget) as total_budget",
            group="department",
            order="total_budget DESC",
            limit=20,
        )

        # Revenue by department
        revenue = await self.socrata.fetch(
            self.datasets["budget"],
            where="revenue_or_spending = 'Revenue'",
            select="department, sum(budget) as total_budget",
            group="department",
            order="total_budget DESC",
            limit=20,
        )

        total_spending = sum(float(r.get("total_budget", 0)) for r in spending)
        total_revenue = sum(float(r.get("total_budget", 0)) for r in revenue)

        return {
            "total_spending": total_spending,
            "total_revenue": total_revenue,
            "top_spending_depts": [
                {"department": r.get("department", "Unknown"), "budget": float(r.get("total_budget", 0))}
                for r in spending[:10]
            ],
            "top_revenue_depts": [
                {"department": r.get("department", "Unknown"), "budget": float(r.get("total_budget", 0))}
                for r in revenue[:10]
            ],
            "_counts": {
                "total_spending": f"${total_spending:,.0f}",
                "total_revenue": f"${total_revenue:,.0f}",
            },
        }

    def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
        def fmt(n):
            return f"${n:,.0f}"

        summary = f"""San Francisco City Budget:
Total Spending: {fmt(data['total_spending'])}
Total Revenue: {fmt(data['total_revenue'])}

Top spending departments:
{chr(10).join(f"- {d['department']}: {fmt(d['budget'])}" for d in data['top_spending_depts'])}

Top revenue departments:
{chr(10).join(f"- {d['department']}: {fmt(d['budget'])}" for d in data['top_revenue_depts'])}"""

        prompt = """As an Expert Data Analyst, analyze this budget data for a dashboard focused on equitable resident spending.
Identify departments with unusually high spending, potential misallocations,
or areas where spending doesn't align with community needs.
Recommend budget advocacy priorities for San Francisco taxpayers."""

        return summary, prompt
