import httpx
from datetime import datetime, timedelta


class SocrataClient:
    BASE_URL = "https://data.sfgov.org/resource"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=60.0)

    async def fetch(
        self,
        dataset_id: str,
        where: str | None = None,
        select: str | None = None,
        group: str | None = None,
        order: str | None = None,
        limit: int = 1000,
    ) -> list[dict]:
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

    async def close(self):
        await self._client.aclose()
