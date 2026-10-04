from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from cre_brain.knowledge.models import Resource, public_url


class FetchError(ValueError):
    pass


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class Download:
    body: bytes
    final_url: str


class Transport(Protocol):
    def get(self, url: str, *, timeout: float, max_bytes: int) -> Response: ...


def is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return False
    return address.is_global and not address.is_multicast and not address.is_reserved


def resolve_public(host: str, timeout: float) -> str:
    code = (
        "import json,socket,sys;"
        "print(json.dumps(sorted({x[4][0] for x in "
        "socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM)})))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", code, host],
            capture_output=True,
            timeout=min(timeout, 5),
            check=True,
            env={},
        )
        addresses = json.loads(result.stdout)
        if not addresses or not all(isinstance(a, str) and is_public_address(a) for a in addresses):
            raise FetchError("DNS destination is not public")
        return str(addresses[0])
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise FetchError("Public DNS resolution failed") from exc


class PublicHTTPS:
    """Pin a validated public IP while verifying TLS against the original hostname.

    No proxy environment, cookies, auth, netrc, Referer or caller-controlled headers.
    """

    def get(self, url: str, *, timeout: float, max_bytes: int) -> Response:
        public_url(url)
        host = urlsplit(url).hostname
        assert host is not None
        deadline = time.monotonic() + timeout
        ip = resolve_public(host, timeout)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchError("Download timeout")
        connection = http.client.HTTPSConnection(host, timeout=remaining)
        watchdog: threading.Timer | None = None
        try:
            raw = socket.create_connection((ip, 443), timeout=remaining)
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise FetchError("Download timeout")
                raw.settimeout(remaining)
                connection.sock = ssl.create_default_context().wrap_socket(
                    raw, server_hostname=host
                )
            except BaseException:
                raw.close()
                raise
            sock = connection.sock

            def interrupt() -> None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

            watchdog = threading.Timer(max(0.001, deadline - time.monotonic()), interrupt)
            watchdog.daemon = True
            watchdog.start()
            sock.settimeout(max(0.001, deadline - time.monotonic()))
            connection.request(
                "GET",
                urlsplit(url).path or "/",
                headers={
                    "User-Agent": "CRE-Knowledge/1.0 (bounded public reference importer)",
                    "Accept": "application/pdf",
                    "Accept-Encoding": "identity",
                },
            )
            sock.settimeout(max(0.001, deadline - time.monotonic()))
            with connection.getresponse() as response:
                headers = {key.lower(): value for key, value in response.getheaders()}
                if response.status != 200:
                    return Response(response.status, headers, b"")
                validate_headers(headers, max_bytes)
                body = bytearray()
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise FetchError("Download timeout")
                    sock.settimeout(remaining)
                    piece = response.read1(min(65536, max_bytes + 1 - len(body)))
                    if not piece:
                        break
                    body.extend(piece)
                    if len(body) > max_bytes:
                        raise FetchError("Download exceeds size limit")
                return Response(response.status, headers, bytes(body))
        except (OSError, http.client.HTTPException) as exc:
            raise FetchError("HTTPS download failed; check source availability") from exc
        finally:
            if watchdog is not None:
                watchdog.cancel()
            connection.close()


def validate_headers(headers: dict[str, str], max_bytes: int) -> None:
    if headers.get("content-type", "").split(";")[0].strip().lower() != "application/pdf":
        raise FetchError("Expected PDF content-type; challenge/HTML pages are prohibited")
    if headers.get("content-encoding", "identity").lower() != "identity":
        raise FetchError("Compressed HTTP responses are prohibited")
    try:
        length = int(headers.get("content-length", "0"))
    except ValueError as exc:
        raise FetchError("Invalid content length") from exc
    if length < 0 or length > max_bytes:
        raise FetchError("Download exceeds size limit")


class BoundedFetcher:
    def __init__(
        self,
        *,
        transport: Transport | None = None,
        max_bytes: int = 25_000_000,
        timeout: float = 30,
    ) -> None:
        if not 1 <= max_bytes <= 25_000_000 or not 0 < timeout <= 60:
            raise ValueError("Fetcher requires bounded positive size and timeout")
        self.transport = transport if transport is not None else PublicHTTPS()
        self.max_bytes = max_bytes
        self.timeout = timeout

    def fetch(self, resource: Resource) -> Download:
        if resource.disposition != "DOWNLOAD_ALLOWED" or not resource.commercial_reuse_allowed:
            raise FetchError("REFERENCE_ONLY cannot be fetched")
        url = resource.download_url
        assert url is not None
        deadline = time.monotonic() + self.timeout
        for _ in range(4):
            try:
                public_url(url)
            except ValueError as exc:
                raise FetchError("Unsafe redirect URL") from exc
            if url not in resource.allowed_urls:
                raise FetchError("Redirect destination is not explicitly allowlisted")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FetchError("Download timeout")
            response = self.transport.get(url, timeout=remaining, max_bytes=self.max_bytes)
            if time.monotonic() > deadline:
                raise FetchError("Download timeout")
            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    raise FetchError("Redirect lacks location")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise FetchError(f"Source returned HTTP {response.status}; no artifact imported")
            validate_headers(response.headers, self.max_bytes)
            if len(response.body) > self.max_bytes:
                raise FetchError("Download exceeds size limit")
            if not response.body.startswith(b"%PDF-"):
                raise FetchError("Expected PDF signature; no artifact imported")
            return Download(response.body, url)
        raise FetchError("Too many redirects")
