"""Config-driven Socrata agent.

Replaces SFPDAgent / SFMTAAgent / PublicWorksAgent / BudgetAgent /
PlanningAgent — they were 90% identical boilerplate around the same
fetch_trends / fetch_recent / group-by pattern. Each domain is now a
SocrataAgentSpec; the runtime base class reads the spec and does the work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from .base import CityAgent


@dataclass(frozen=True)
class GroupByQuery:
    """A `select X, count(*) as cnt group by X order by cnt DESC` query."""

    column: str           # field to group by
    label_key: str        # output label (e.g. "category", "violation")
    days: int = 30
    limit: int = 10
    extra_where: Optional[str] = None


@dataclass(frozen=True)
class TrendQuery:
    days: int = 180
    period: str = "month"


@dataclass(frozen=True)
class StaticQuery:
    """A fixed where-clause aggregation (no recency filter), e.g. budget totals."""

    where: str
    select: str
    group: str
    order: str
    limit: int = 20


@dataclass(frozen=True)
class SocrataAgentSpec:
    name: str
    department: str
    icon: str
    news_query: str
    dataset_id: str
    date_field: str
    officials: Sequence[dict]
    counts_label: str                                    # key for _counts dict
    summary_builder: Callable[[dict], str]               # data -> human-readable summary
    analysis_prompt: str
    trend: Optional[TrendQuery] = None
    breakdowns: tuple[GroupByQuery, ...] = field(default_factory=tuple)
    static_queries: tuple[tuple[str, StaticQuery], ...] = field(default_factory=tuple)


def build_socrata_agent(spec: SocrataAgentSpec) -> type[CityAgent]:
    """Construct a CityAgent subclass from a spec."""

    class _SocrataAgent(CityAgent):
        name = spec.name
        department = spec.department
        icon = spec.icon
        news_query = spec.news_query
        datasets = {"primary": spec.dataset_id}
        officials = list(spec.officials)

        async def fetch_data(self) -> dict:
            data: dict = {}

            if spec.trend is not None:
                trends = await self.socrata.fetch_trends(
                    spec.dataset_id,
                    date_field=spec.date_field,
                    days=spec.trend.days,
                    period=spec.trend.period,
                )
                data["monthly_trends"] = [
                    {"month": (r.get("period", "") or "").split("T")[0][:7],
                     "count": int(r.get("cnt", 0))}
                    for r in trends
                ]

            for query in spec.breakdowns:
                kwargs = dict(
                    date_field=spec.date_field,
                    days=query.days,
                    select=f"{query.column}, count(*) as cnt",
                    group=query.column,
                    order="cnt DESC",
                    limit=query.limit,
                )
                if query.extra_where:
                    kwargs["where"] = query.extra_where
                rows = await self.socrata.fetch_recent(spec.dataset_id, **kwargs)
                key = f"by_{query.label_key}"
                data[key] = [
                    {query.label_key: r.get(query.column, "Unknown"),
                     "count": int(r.get("cnt", 0))}
                    for r in rows
                ]

            for key, sq in spec.static_queries:
                rows = await self.socrata.fetch(
                    spec.dataset_id,
                    where=sq.where,
                    select=sq.select,
                    group=sq.group,
                    order=sq.order,
                    limit=sq.limit,
                )
                data[key] = rows

            data["_counts"] = {spec.counts_label: _summarize_counts(data)}
            return data

        def build_analysis_prompt(self, data: dict) -> tuple[str, str]:
            return spec.summary_builder(data), spec.analysis_prompt

    _SocrataAgent.__name__ = f"{spec.name.replace(' ', '')}Agent"
    _SocrataAgent.__qualname__ = _SocrataAgent.__name__
    return _SocrataAgent


def _summarize_counts(data: dict) -> int | str:
    """Best-effort headline count from whichever shape the data has."""
    for key, value in data.items():
        if key.startswith("by_") and isinstance(value, list):
            return sum(item.get("count", 0) for item in value)
    for key, value in data.items():
        if key == "_counts" or not isinstance(value, list):
            continue
        if value and isinstance(value[0], dict) and "total_budget" in value[0]:
            total = sum(float(r.get("total_budget", 0)) for r in value)
            return f"${total:,.0f}"
    return 0
