import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


MAX_URL_LENGTH = 2048


def parse_allowed_user_ids(raw_value: str) -> frozenset[int]:
    user_ids = set()
    for value in raw_value.split(","):
        value = value.strip()
        if not value:
            continue
        user_id = int(value)
        if user_id <= 0:
            raise ValueError("Telegram user IDs must be positive integers")
        user_ids.add(user_id)
    return frozenset(user_ids)


def _resolved_addresses(hostname: str, port: int) -> tuple[str, ...]:
    return tuple(
        address[4][0]
        for address in socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    )


def is_safe_public_http_url(url: str) -> bool:
    return _is_safe_public_url(url, {"http", "https"})


def is_safe_public_websocket_url(url: str) -> bool:
    return _is_safe_public_url(url, {"ws", "wss"})


def _is_safe_public_url(url: str, allowed_schemes: set[str]) -> bool:
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        return False

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False

    if parsed.scheme.lower() not in allowed_schemes:
        return False
    if not parsed.hostname or parsed.username or parsed.password:
        return False

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return False

    try:
        addresses = (hostname,) if _is_ip_address(hostname) else _resolved_addresses(
            hostname,
            port or (443 if parsed.scheme.lower() in {"https", "wss"} else 80),
        )
    except OSError:
        return False

    return bool(addresses) and all(
        ipaddress.ip_address(address).is_global for address in addresses
    )


def url_for_log(url: str) -> str:
    try:
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.hostname:
            return "<invalid URL>"
        port = f":{parsed.port}" if parsed.port else ""
        return urlunsplit(
            (
                parsed.scheme,
                f"{parsed.hostname}{port}",
                parsed.path,
                "",
                "",
            )
        )[:200]
    except ValueError:
        return "<invalid URL>"


def _is_ip_address(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False
