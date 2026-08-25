"""Safe HTML retrieval and extraction behind the platform tool contract."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from hashlib import sha256

import httpx
import trafilatura

from app.web_research.contracts import Evidence, ToolPolicyError
from app.web_research.policy import (
    MAX_EXTRACTED_TEXT_CHARS,
    MAX_REDIRECTS,
    MAX_RESPONSE_BYTES,
    validate_public_destination,
    validate_response_headers,
)


class WebExtractor:
    """Retrieve a public HTML page and return bounded, normalized evidence."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        destination_validator: Callable[[str], Awaitable[None]] = validate_public_destination,
    ) -> None:
        self._client = client
        self._destination_validator = destination_validator

    async def extract(self, requested_url: str) -> Evidence:
        """Fetch one public page without following uncontrolled redirects."""

        current_url = requested_url
        for _ in range(MAX_REDIRECTS + 1):
            await self._destination_validator(current_url)
            async with self._client.stream("GET", current_url, follow_redirects=False) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ToolPolicyError(
                            "The redirect response did not provide a destination."
                        )
                    current_url = str(response.url.join(location))
                    continue

                response.raise_for_status()
                content_type = validate_response_headers(
                    response.headers.get("content-type"),
                    response.headers.get("content-disposition"),
                )
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        declared_size = int(content_length)
                    except ValueError as error:
                        raise ToolPolicyError(
                            "The response declared an invalid content length."
                        ) from error
                    if declared_size > MAX_RESPONSE_BYTES:
                        raise ToolPolicyError("The response exceeds the maximum permitted size.")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise ToolPolicyError("The response exceeds the maximum permitted size.")
                return self._to_evidence(response, content_type, bytes(content))

        raise ToolPolicyError("The request exceeded the maximum number of redirects.")

    @staticmethod
    def _to_evidence(
        response: httpx.Response, content_type: str, raw_content: bytes
    ) -> Evidence:
        if content_type == "text/plain":
            text = raw_content.decode(response.encoding or "utf-8", errors="replace").strip()
            extraction_method = "plain-text"
        else:
            text = trafilatura.extract(
                raw_content,
                url=str(response.url),
                output_format="txt",
                include_comments=False,
                include_tables=True,
            ) or ""
            extraction_method = "trafilatura"

        if not text:
            raise ToolPolicyError("No extractable text was found in the response.")
        if len(text) > MAX_EXTRACTED_TEXT_CHARS:
            raise ToolPolicyError("The extracted text exceeds the maximum permitted size.")
        return Evidence(
            url=str(response.url),
            retrieved_at=datetime.now(UTC),
            content_type=content_type,
            text=text,
            content_hash=f"sha256:{sha256(raw_content).hexdigest()}",
            extraction_method=extraction_method,
        )
