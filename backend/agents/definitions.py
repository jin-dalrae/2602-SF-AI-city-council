"""Concrete Socrata-backed agents.

Each agent is a SocrataAgentSpec — declarative config plus a small summary
builder. The runtime class is produced by `build_socrata_agent` in
socrata_agent.py.
"""

from __future__ import annotations

from .socrata_agent import (
    GroupByQuery,
    SocrataAgentSpec,
    StaticQuery,
    TrendQuery,
    build_socrata_agent,
)


def _trend_lines(data: dict, unit: str) -> str:
    rows = data.get("monthly_trends", [])
    return "\n".join(f"- {t['month']}: {t['count']} {unit}" for t in rows)


def _breakdown_lines(data: dict, key: str, label: str) -> str:
    rows = data.get(f"by_{key}", [])
    return "\n".join(f"- {r[key]}: {r['count']} {label}" for r in rows)


# ── Safety Commissioner (SFPD) ──────────────────────────────────────────────

def _sfpd_summary(data: dict) -> str:
    total = sum(r["count"] for r in data.get("by_category", []))
    return f"""San Francisco Incident Analysis:

Monthly Incident Trends (Last 90 Days):
{_trend_lines(data, 'incidents')}

Recent 30-Day Snapshot:
Total incidents: {total}

Top Categories (Last 30 Days):
{_breakdown_lines(data, 'category', '')}

Incidents by District (Last 30 Days):
{_breakdown_lines(data, 'district', '')}"""


SFPD_SPEC = SocrataAgentSpec(
    name="Safety Commissioner",
    department="Police Department",
    icon="shield",
    news_query="San Francisco crime safety public safety policy 2026",
    dataset_id="wg3w-h783",
    date_field="incident_date",
    officials=[
        {"name": "Bill Scott", "title": "Chief of Police", "email": "sfpdchief@sfgov.org"},
        {"name": "Cindy Elias", "title": "Police Commission President", "email": "policecommission@sfgov.org"},
    ],
    counts_label="last_30d_incidents",
    trend=TrendQuery(days=90, period="week"),
    breakdowns=(
        GroupByQuery(column="incident_category", label_key="category", days=30, limit=10),
        GroupByQuery(column="police_district", label_key="district", days=30, limit=10),
    ),
    summary_builder=_sfpd_summary,
    analysis_prompt="""As an Expert Data Analyst, identify significant shifts in public safety.
Look at the Monthly Incident Trends: are incidents increasing month-over-month?
Cross-reference the Top Categories with the Districts: which areas are seeing specific types of crime increase?
Identify trends that require immediate community intervention or policy adjustment.""",
)


# ── Transit Authority (SFMTA) ───────────────────────────────────────────────

def _sfmta_summary(data: dict) -> str:
    total = sum(r["count"] for r in data.get("by_violation", []))
    return f"""SFMTA Transit Citation Analysis:

Monthly Citation Trends (Last 6 Months):
{_trend_lines(data, 'citations')}

Recent 30-Day Snapshot:
Total citations: {total}

Violation Categories (Last 30 Days):
{_breakdown_lines(data, 'violation', '')}"""


SFMTA_SPEC = SocrataAgentSpec(
    name="Transit Authority",
    department="Municipal Transportation Agency",
    icon="bus",
    news_query="San Francisco Muni transit SFMTA service performance equity 2026",
    dataset_id="8pxu-u28x",
    date_field="citation_issued_datetime",
    officials=[
        {"name": "Jeffrey Tumlin", "title": "SFMTA Director of Transportation", "email": "mtadirector@sfmta.com"},
    ],
    counts_label="last_30d_citations",
    trend=TrendQuery(days=180, period="month"),
    breakdowns=(
        GroupByQuery(column="violation_desc", label_key="violation", days=30, limit=10),
    ),
    summary_builder=_sfmta_summary,
    analysis_prompt="""As an Expert Data Analyst, analyze the trajectory of transit enforcement.
Identify if citations are increasing month-over-month.
Consider the impact of these enforcement trends on transit equity and low-income riders.
Recommend policy changes based on the observed data patterns.""",
)


# ── Infrastructure Foreman (311 / Public Works) ─────────────────────────────

def _public_works_summary(data: dict) -> str:
    total = sum(r["count"] for r in data.get("by_category", []))
    open_rows = data.get("open_backlog", [])
    open_count = sum(int(r.get("cnt", 0)) for r in open_rows)
    backlog_lines = "\n".join(
        f"- {r.get('service_name', 'Unknown')}: {r.get('cnt', 0)} open"
        for r in open_rows[:5]
    )
    return f"""SF 311 Service Requests Analysis:

Monthly Volume Trends (Last 6 Months):
{_trend_lines(data, 'requests')}

Recent 30-Day Snapshot:
Total requests: {total}

Top request categories (Last 30 Days):
{_breakdown_lines(data, 'category', '')}

Current Backlogs (Open cases):
{backlog_lines}"""


PUBLIC_WORKS_SPEC = SocrataAgentSpec(
    name="Infrastructure Foreman",
    department="Public Works",
    icon="wrench",
    news_query="San Francisco 311 public works infrastructure maintenance 2026",
    dataset_id="vw6y-z8j6",
    date_field="requested_datetime",
    officials=[
        {"name": "Carla Short", "title": "Director of Public Works", "email": "dpw@sfgov.org"},
    ],
    counts_label="last_30d",
    trend=TrendQuery(days=180, period="month"),
    breakdowns=(
        GroupByQuery(column="service_name", label_key="category", days=30, limit=10),
        GroupByQuery(column="status_description", label_key="status", days=30, limit=5),
    ),
    static_queries=(
        (
            "open_backlog",
            StaticQuery(
                where="status_description = 'Open'",
                select="service_name, count(*) as cnt",
                group="service_name",
                order="cnt DESC",
                limit=5,
            ),
        ),
    ),
    summary_builder=_public_works_summary,
    analysis_prompt="""As an Expert Data Analyst, identify significant shifts in city service demand.
Look at the Monthly Volume Trends: are requests surfacing faster than they are being closed?
Identify specific categories (like Potholes or Graffiti) where the backlog is disproportionately high compared to monthly volume.
Provide a trend-based analysis of department performance.""",
)


# ── City Comptroller (Budget) ───────────────────────────────────────────────

def _budget_summary(data: dict) -> str:
    def fmt(n: float) -> str:
        return f"${n:,.0f}"

    spending = data.get("spending", [])
    revenue = data.get("revenue", [])
    total_spending = sum(float(r.get("total_budget", 0)) for r in spending)
    total_revenue = sum(float(r.get("total_budget", 0)) for r in revenue)

    spend_lines = "\n".join(
        f"- {r.get('department', 'Unknown')}: {fmt(float(r.get('total_budget', 0)))}"
        for r in spending[:10]
    )
    rev_lines = "\n".join(
        f"- {r.get('department', 'Unknown')}: {fmt(float(r.get('total_budget', 0)))}"
        for r in revenue[:10]
    )
    return f"""San Francisco City Budget:
Total Spending: {fmt(total_spending)}
Total Revenue: {fmt(total_revenue)}

Top spending departments:
{spend_lines}

Top revenue departments:
{rev_lines}"""


BUDGET_SPEC = SocrataAgentSpec(
    name="City Comptroller",
    department="Office of the Controller",
    icon="dollar-sign",
    news_query="San Francisco city budget spending fiscal policy 2026",
    dataset_id="xdgd-c79v",
    date_field="",  # No date filter for budget aggregates.
    officials=[
        {"name": "Greg Wagner", "title": "City Controller", "email": "controller@sfgov.org"},
        {"name": "Anna Van Degna", "title": "Director of the Office of Public Finance", "email": "budget.analyst@sfgov.org"},
    ],
    counts_label="total_spending",
    static_queries=(
        (
            "spending",
            StaticQuery(
                where="revenue_or_spending = 'Spending'",
                select="department, sum(budget) as total_budget",
                group="department",
                order="total_budget DESC",
                limit=20,
            ),
        ),
        (
            "revenue",
            StaticQuery(
                where="revenue_or_spending = 'Revenue'",
                select="department, sum(budget) as total_budget",
                group="department",
                order="total_budget DESC",
                limit=20,
            ),
        ),
    ),
    summary_builder=_budget_summary,
    analysis_prompt="""As an Expert Data Analyst, analyze this budget data for a dashboard focused on equitable resident spending.
Identify departments with unusually high spending, potential misallocations,
or areas where spending doesn't align with community needs.
Recommend budget advocacy priorities for San Francisco taxpayers.""",
)


# ── Planning Commissioner (Permits) ─────────────────────────────────────────

def _planning_summary(data: dict) -> str:
    total = sum(r["count"] for r in data.get("by_type", []))
    return f"""SF Building Permits (Last 90 Days):
Total permits filed: {total}

Permits by type:
{_breakdown_lines(data, 'type', '')}

Permits by status:
{_breakdown_lines(data, 'status', '')}"""


PLANNING_SPEC = SocrataAgentSpec(
    name="Planning Commissioner",
    department="Planning Department",
    icon="building",
    news_query="San Francisco housing development building permits zoning 2026",
    dataset_id="i98e-djp9",
    date_field="filed_date",
    officials=[
        {"name": "Rich Hillis", "title": "Planning Director", "email": "planning@sfgov.org"},
    ],
    counts_label="total_permits_90d",
    breakdowns=(
        GroupByQuery(column="permit_type_definition", label_key="type", days=90, limit=15),
        GroupByQuery(column="status", label_key="status", days=90, limit=10),
    ),
    summary_builder=_planning_summary,
    analysis_prompt="""As an Expert Data Analyst, analyze building permit data for a citizen oversight dashboard.
Identify trends in permit types, approval bottlenecks, and housing development patterns.
Recommend policy actions to improve housing affordability and community-focused development.""",
)


SFPDAgent = build_socrata_agent(SFPD_SPEC)
SFMTAAgent = build_socrata_agent(SFMTA_SPEC)
PublicWorksAgent = build_socrata_agent(PUBLIC_WORKS_SPEC)
BudgetAgent = build_socrata_agent(BUDGET_SPEC)
PlanningAgent = build_socrata_agent(PLANNING_SPEC)
