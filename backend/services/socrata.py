import httpx
from datetime import datetime, timedelta


class SocrataClient:
    BASE_URL = "https://data.sfgov.org/resource"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=60.0)
        self._metadata_cache: dict[str, int] = {}  # dataset_id -> last_updated_timestamp

    async def needs_update(self, dataset_id: str) -> bool:
        """Check if the dataset has been updated since last fetch."""
        try:
            url = f"https://data.sfgov.org/api/views/{dataset_id}.json"
            resp = await self._client.get(url)
            resp.raise_for_status()
            metadata = resp.json()
            # Use 'rowsUpdatedAt' as it's the most reliable for data changes
            updated_at = metadata.get("rowsUpdatedAt", 0)
            
            if dataset_id not in self._metadata_cache or updated_at > self._metadata_cache[dataset_id]:
                self._metadata_cache[dataset_id] = updated_at
                return True
            return False
        except Exception as e:
            print(f"Error checking metadata for {dataset_id}: {e}")
            return True # Default to update if check fails

    async def fetch(
        self,
        dataset_id: str,
        where: str | None = None,
        select: str | None = None,
        group: str | None = None,
        order: str | None = None,
        limit: int = 1000,
        force_update: bool = False
    ) -> list[dict]:
        # Check if update is needed unless forced
        if not force_update:
            if not await self.needs_update(dataset_id):
                # If we were strictly following PRD, we might return cached data here.
                # For now, let's just proceed or return None if we want to skip.
                # However, many agents fetch once and store. The 'marathon' requirement
                # says agents run every 60s. 
                pass

        url = f"{self.BASE_URL}/{dataset_id}.json"
        params: dict[str, str] = {"$limit": str(limit)}
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select
        if group:
            params["$group"] = group
        if order:
            params["$order"] = order

        resp = await self._client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def fetch_recent(
        self,
        dataset_id: str,
        date_field: str,
        days: int = 90,
        **kwargs,
    ) -> list[dict]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
        where = f"{date_field} > '{cutoff}'"
        if kwargs.get("where"):
            where = f"{where} AND ({kwargs.pop('where')})"
        return await self.fetch(dataset_id, where=where, **kwargs)

    async def fetch_trends(
        self,
        dataset_id: str,
        date_field: str,
        days: int = 180,
        period: str = "month", # "month", "week", "day"
        **kwargs
    ) -> list[dict]:
        """Fetch counts grouped by time period for trend analysis."""
        trunc_func = "date_trunc_ym" if period == "month" else "date_trunc_ywd" if period == "week" else "date_trunc_y"
        if period == "day": trunc_func = "date_trunc_yd"
        
        select = f"{trunc_func}({date_field}) as period, count(*) as cnt"
        group = "period"
        order = "period DESC"
        
        return await self.fetch_recent(
            dataset_id, 
            date_field=date_field, 
            days=days, 
            select=select, 
            group=group, 
            order=order,
            **kwargs
        )

    async def close(self):
        await self._client.aclose()
