"""SearXNG adapter behind the platform's bounded discovery contract."""

from collections.abc import Mapping
from typing import Any

import httpx

from app.web_research.contracts import SearchResponse, SearchResult, ToolProviderError
from app.web_research.policy import validate_public_url


class SearxngSearchProvider:
    """Translate SearXNG JSON results into platform-owned source candidates."""

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str, max_results: int) -> SearchResponse:
        """Search through the internal SearXNG service with bounded output."""

        try:
            response = await self._client.get(
                f"{self._base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": "general",
                    "safesearch": "1",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ToolProviderError("The search provider is unavailable.") from error

        raw_results = payload.get("results", []) if isinstance(payload, Mapping) else []
        results: list[SearchResult] = []
        for raw_result in raw_results:
            candidate = self._normalize_result(raw_result)
            if candidate is not None:
                results.append(candidate)
            if len(results) == max_results:
                break
        return SearchResponse(query=query, results=results)

    @staticmethod
    def _normalize_result(raw_result: Any) -> SearchResult | None:
        if not isinstance(raw_result, Mapping):
            return None
        url = raw_result.get("url")
        title = raw_result.get("title")
        if not isinstance(url, str) or not isinstance(title, str) or not title.strip():
            return None
        try:
            validate_public_url(url)
        except ToolProviderError:
            return None
        except ValueError:
            return None
        snippet = raw_result.get("content")
        engine = raw_result.get("engine")
        return SearchResult(
            title=title.strip()[:512],
            url=url,
            snippet=snippet.strip()[:2_000] if isinstance(snippet, str) else "",
            engine=engine.strip()[:128] if isinstance(engine, str) else None,
        )
