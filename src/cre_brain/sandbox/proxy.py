"""HTTPS CONNECT allowlist with pinned, exclusively public DNS answers."""

from __future__ import annotations

import ipaddress
import os
import re
import select
import socket
import socketserver
from collections.abc import Callable, Sequence
from typing import Any


def validate_domains(domains: Sequence[str]) -> tuple[str, ...]:
    for domain in domains:
        if not re.fullmatch(
            r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", domain
        ):
            raise ValueError("Allowlist requires exact lowercase DNS names, not URLs/wildcards")
        try:
            ipaddress.ip_address(domain)
        except ValueError:
            continue
        raise ValueError("IP literals cannot be allowlisted")
    return tuple(sorted(set(domains)))


def resolve_target(
    authority: str,
    domains: Sequence[str],
    *,
    resolver: Callable[..., Any] = socket.getaddrinfo,
) -> tuple[str, int]:
    host, separator, port = authority.rpartition(":")
    if not separator or port != "443" or host not in domains:
        raise ValueError("Destination is not allowlisted HTTPS")
    answers = resolver(host, 443, type=socket.SOCK_STREAM)
    addresses = [str(answer[4][0]) for answer in answers]
    parsed = [ipaddress.ip_address(address) for address in addresses]
    if not parsed or any(not a.is_global or a.is_multicast or a.is_reserved for a in parsed):
        raise ValueError("Non-public DNS address rejected")
    return str(sorted(parsed, key=lambda a: a.version)[0]), 443


class ConnectHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.connection.settimeout(10)
        try:
            line = self.rfile.readline(4097)
            if len(line) > 4096:
                raise ValueError("Request too large")
            method, authority, version = line.decode("ascii").strip().split(" ")
            if method != "CONNECT" or version not in ("HTTP/1.0", "HTTP/1.1"):
                raise ValueError("Only HTTPS CONNECT is allowed")
            count = 0
            while True:
                header = self.rfile.readline(4097)
                count += len(header)
                if count > 16384 or not header:
                    raise ValueError("Invalid headers")
                if header == b"\r\n":
                    break
            target = resolve_target(
                authority, validate_domains(os.environ.get("ALLOW_DOMAINS", "").split())
            )
            # Connect to the validated address, never resolve the hostname a second time.
            with socket.create_connection(target, timeout=10) as upstream:
                self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self.wfile.flush()
                while True:
                    ready, _, _ = select.select([self.connection, upstream], [], [], 60)
                    if not ready:
                        return
                    for source in ready:
                        chunk = source.recv(65536)
                        if not chunk:
                            return
                        (upstream if source is self.connection else self.connection).sendall(chunk)
        except (ValueError, UnicodeError, OSError):
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")


class ProxyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    validate_domains(os.environ.get("ALLOW_DOMAINS", "").split())
    with ProxyServer(("127.0.0.1", 3128), ConnectHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
