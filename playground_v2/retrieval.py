"""Bounded public HTTP retrieval, retained from the verified prototype."""
import ipaddress
import re
import socket
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
import requests
import urllib3

MAX_BYTES = 20 * 1024 * 1024
USER_AGENT = "PaperToPlayground/2.0 (public academic source retrieval)"


class SourceError(ValueError):
    """A paper could not be obtained as dependable text."""


def _public_destination(url: str) -> tuple[str, int, list[str]]:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise SourceError("Only public HTTP(S) sources are supported")
    if parsed.username is not None or parsed.password is not None:
        raise SourceError("Source URLs cannot contain credentials")
    hostname = parsed.hostname.encode("idna").decode("ascii")
    if hostname.lower().rstrip(".") == "localhost" or hostname.lower().endswith((".localhost", ".local", ".internal")):
        raise SourceError("Private source destinations are not permitted")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise SourceError("Invalid source port") from exc
    if port not in (80, 443):
        raise SourceError("Source URLs must use public web ports 80 or 443")
    try:
        addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)))
    except socket.gaierror as exc:
        raise SourceError("Source hostname could not be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise SourceError("Source resolves to a non-public network address")
    return hostname, port, addresses


def _fetch(url: str, deadline: float) -> tuple[bytes, str, str]:
    current = url
    for redirect in range(6):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SourceError("Source retrieval exceeded its time allowance")
        hostname, port, addresses = _public_destination(current)
        parsed = urlsplit(current)
        path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        # Connect to an already-validated IP. TLS still checks the original
        # hostname, avoiding a second DNS lookup and a rebinding race.
        pool_args = {"host": addresses[0], "port": port, "maxsize": 1, "block": False}
        if parsed.scheme == "https":
            pool = urllib3.HTTPSConnectionPool(**pool_args, server_hostname=hostname,
                                               assert_hostname=hostname, cert_reqs="CERT_REQUIRED",
                                               ca_certs=requests.certs.where())
        else:
            pool = urllib3.HTTPConnectionPool(**pool_args)
        response = None
        try:
            response = pool.urlopen("GET", path, headers={"User-Agent": USER_AGENT,
                                   "Host": hostname, "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.1",
                                   "Accept-Encoding": "gzip,deflate"},
                                   preload_content=False, redirect=False, retries=False,
                                   timeout=urllib3.Timeout(total=remaining, connect=min(8, remaining), read=min(8, remaining)))
            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    raise SourceError("Source redirect has no destination")
                if redirect == 5:
                    raise SourceError("Source exceeded five redirects")
                current = urljoin(current, location)
                continue
            if response.status != 200:
                raise SourceError(f"Source returned HTTP {response.status}")
            length = response.headers.get("Content-Length", "")
            if length.isdecimal() and int(length) > MAX_BYTES:
                raise SourceError("Source is larger than 20 MiB")
            chunks, total = [], 0
            for chunk in response.stream(65536, decode_content=True):
                if time.monotonic() >= deadline:
                    raise SourceError("Source retrieval exceeded its time allowance")
                total += len(chunk)
                if total > MAX_BYTES:
                    raise SourceError("Decoded source is larger than 20 MiB")
                chunks.append(chunk)
            return b"".join(chunks), current, response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        except (urllib3.exceptions.HTTPError, OSError) as exc:
            raise SourceError(f"Source connection failed ({type(exc).__name__})") from exc
        finally:
            if response is not None:
                response.close()
            pool.close()
    raise SourceError("Source redirect limit exceeded")


def _arxiv_identity(url: str) -> tuple[str | None, str | None]:
    parsed = urlsplit(url)
    if (parsed.hostname or "").lower() not in ("arxiv.org", "www.arxiv.org", "export.arxiv.org"):
        return None, None
    match = re.match(r"^/(?:abs|html|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?|[a-z.-]+/\d{7}(?:v\d+)?)(?:\.pdf)?/?$", parsed.path, re.I)
    if not match:
        return None, None
    paper_id = match.group(1)
    version = re.search(r"v(\d+)$", paper_id)
    return paper_id, f"v{version.group(1)}" if version else None
