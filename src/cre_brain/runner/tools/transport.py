"""Minimal newline-delimited MCP stdio, without optional runtime imports.

Supports initialize, notifications/initialized, ping, tools/list and tools/call.
Tool results contain the exact canonical CLI JSON text. No resources, prompts,
HTTP, sampling or model calls. This module claims offline protocol plumbing only.
"""

from typing import Any, TextIO

from cre_brain.runner.tools.json_io import MAX_BYTES, canonical, parse
from cre_brain.runner.tools.registry import ToolRegistry, refused

VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


def _error(identity: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": identity, "error": {"code": code, "message": message}}


def handle_message(registry: ToolRegistry, message: dict[str, Any]) -> dict[str, Any] | None:
    identity = message.get("id")
    try:
        message = parse(canonical(message))
        if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return _error(identity, -32600, "Invalid bounded JSON-RPC request")
        if set(message) - {"jsonrpc", "id", "method", "params"} or type(identity) not in {
            int,
            str,
            type(None),
        }:
            return _error(None, -32600, "Invalid JSON-RPC envelope")
        if "id" not in message:
            return None
        method = message["method"]
        params = message.get("params", {})
        if not isinstance(params, dict):
            return _error(identity, -32602, "Parameters must be an object")
        if method == "initialize":
            version = params.get("protocolVersion")
            if version not in VERSIONS:
                return _error(identity, -32602, "Unsupported MCP protocol version")
            result = {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cre", "version": "0.1.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": name,
                        "description": f"Canonical scoped CRE {name} tool",
                        "inputSchema": model.model_json_schema(),
                    }
                    for name, model in registry.tool_models.items()
                ]
            }
        elif method == "tools/call":
            if set(params) - {"name", "arguments", "_meta"} or not isinstance(
                params.get("name"), str
            ):
                return _error(identity, -32602, "Use a canonical tool name and arguments")
            arguments = params.get("arguments", {})
            meta = params.get("_meta", {})
            if not isinstance(arguments, dict) or not isinstance(meta, dict):
                return _error(identity, -32602, "Arguments and metadata must be objects")
            request_id = meta.get("cre/request_id")
            if request_id is not None and not isinstance(request_id, str):
                return _error(identity, -32602, "Request identity must be a string")
            response = registry.call(params["name"], arguments, request_id=request_id)
            result = {
                "content": [{"type": "text", "text": canonical(response)}],
                "isError": response["status"] == "refused",
            }
        else:
            return _error(identity, -32601, "Method not supported by minimal CRE MCP stdio")
        return {"jsonrpc": "2.0", "id": identity, "result": result}
    except (ValueError, RecursionError):
        return _error(identity, -32602, "Invalid bounded JSON-RPC parameters")


def serve(registry: ToolRegistry, stdin: TextIO, stdout: TextIO) -> None:
    while True:
        line = stdin.readline(MAX_BYTES + 1)
        if not line:
            return
        if len(line.encode()) > MAX_BYTES or not line.endswith("\n"):
            stdout.write(
                canonical(_error(None, -32700, "Bounded newline-delimited JSON required")) + "\n"
            )
            stdout.flush()
            return  # Do not parse trailing fragments of an oversized request.
        try:
            response = handle_message(registry, parse(line))
        except (ValueError, RecursionError):
            response = _error(None, -32700, "Invalid bounded JSON")
        if response is not None:
            stdout.write(canonical(response) + "\n")
            stdout.flush()


def missing_context() -> dict[str, Any]:
    return refused(
        "missing_context",
        "Host must inject an authenticated registry; arguments cannot configure authority.",
    )
