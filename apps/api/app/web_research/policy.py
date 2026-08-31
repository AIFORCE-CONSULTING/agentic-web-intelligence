"""Input and destination policy for public, read-only web retrieval."""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from app.web_research.contracts import ToolPolicyError

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain"})
MAX_RESPONSE_BYTES = 2_000_000
MAX_EXTRACTED_TEXT_CHARS = 200_000
MAX_REDIRECTS = 3
MAX_DNS_RESOLUTION_SECONDS = 2.0
Address = ipaddress.IPv4Address | ipaddress.IPv6Address
AddressResolver = Callable[[str, int], Awaitable[set[Address]]]


def validate_public_url(url: str) -> None:
    """Reject URL forms that cannot be fetched by the public-web capability."""

    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ToolPolicyError("Only http and https URLs are permitted.")
    if not parsed.hostname:
        raise ToolPolicyError("A URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ToolPolicyError("URLs with embedded credentials are not permitted.")
    try:
        port = parsed.port
    except ValueError as error:
        raise ToolPolicyError("A URL must include a valid port.") from error
    if port not in (None, 80, 443):
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


async def resolve_hostname(hostname: str, port: int) -> set[Address]:
    """Resolve a hostname through the runtime resolver and return every address."""

    try:
        records = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(
                hostname, port, type=socket.SOCK_STREAM
            ),
            timeout=MAX_DNS_RESOLUTION_SECONDS,
        )
    except TimeoutError as error:
        raise ToolPolicyError("The destination hostname resolution timed out.") from error
    except socket.gaierror as error:
        raise ToolPolicyError("The destination hostname could not be resolved.") from error
    addresses = {ipaddress.ip_address(record[4][0]) for record in records}
    if not addresses:
        raise ToolPolicyError("The destination hostname did not resolve to an address.")
    return addresses


async def validate_public_destination(
    url: str, resolver: AddressResolver = resolve_hostname
) -> None:
    """Validate URL syntax and reject hostnames that resolve to any private address.

    This must run immediately before every request, including each redirect target.
    Rejecting mixed public/private DNS answers avoids leaving address selection to
    the HTTP client's resolver.
    """

    validate_public_url(url)
    parsed = urlparse(url)
    hostname = parsed.hostname
    assert hostname is not None
    try:
        literal_address = ipaddress.ip_address(hostname)
    except ValueError:
        literal_address = None
    if literal_address is not None:
        return

    destination_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = await resolver(hostname.rstrip("."), destination_port)
    if any(not address.is_global for address in addresses):
        raise ToolPolicyError(
            "The destination hostname resolves to a non-public network address."
        )


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
