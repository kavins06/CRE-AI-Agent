"""Private PDF worker: process-local budgets, no inherited secrets, no model/network calls."""

from __future__ import annotations

import json
import resource
import socket
import sys

from cre_brain.extraction.preparse.models import Limits, ParserUnavailable


def _no_network(*args: object, **kwargs: object) -> None:
    raise RuntimeError("Network is disabled for deterministic PDF parsing")


def main() -> None:
    limits = Limits.model_validate_json(sys.argv[1])
    memory = limits.worker_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (limits.worker_cpu_seconds, limits.worker_cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits.max_output_bytes, limits.max_output_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    # Defense in depth, not a substitute for the separate runtime's physical egress policy.
    socket.socket.connect = _no_network  # type: ignore[method-assign]
    socket.socket.connect_ex = _no_network  # type: ignore[method-assign,assignment]
    try:
        from cre_brain.extraction.preparse.pdf import convert_pdf

        raw = sys.stdin.buffer.read(limits.max_file_bytes + 1)
        if len(raw) > limits.max_file_bytes:
            raise ValueError("Input resource limit exceeded")
        result = convert_pdf(raw, limits)
        sys.stdout.write(result.model_dump_json())
    except Exception as error:
        # Do not expose document text, filesystem paths, SDK diagnostics or credentials.
        sys.stdout.write(
            json.dumps(
                {
                    "error": (
                        "unavailable"
                        if isinstance(error, ParserUnavailable)
                        else "invalid_or_over_budget"
                    )
                }
            )
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
