"""Input policy for public, read-only web retrieval."""

import ipaddress
from urllib.parse import urlparse

from app.web_research.contracts import ToolPolicyError


ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain"})
MAX_RESPONSE_BYTES = 2_000_000
MAX_REDIRECTS = 3


def validate_public_url(url: str) -> None:
    """Reject URL forms that cannot be fetched by the public-web capability."""

    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ToolPolicyError("Only http and https URLs are permitted.")
    if not parsed.hostname:
        raise ToolPolicyError("A URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ToolPolicyError("URLs with embedded credentials are not permitted.")
    if parsed.port not in (None, 80, 443):
        raise ToolPolicyError("Only standard web ports are permitted.")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ToolPolicyError("Localhost destinations are not permitted.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return

    if not address.is_global:
        raise ToolPolicyError("Non-public network addresses are not permitted.")


def validate_response_headers(content_type: str | None, content_disposition: str | None) -> str:
    """Allow only bounded, inline text responses from the retrieval service."""

    if content_disposition and "attachment" in content_disposition.lower():
        raise ToolPolicyError("Attachments and file downloads are not permitted.")
    if not content_type:
        raise ToolPolicyError("The response did not declare a supported content type.")

    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise ToolPolicyError(f"Unsupported content type: {media_type}.")
    return media_type
