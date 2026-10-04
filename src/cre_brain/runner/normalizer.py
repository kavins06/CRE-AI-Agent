"""Bounded Codex JSONL normalization, with host identities and pre-storage scrubbing."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import Field, TypeAdapter

from cre_brain.domain import AgentEvent
from cre_brain.domain.models import AgentEventKind
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.tools.contracts import ID, Boundary
from cre_brain.runner.tools.json_io import MAX_BYTES, canonical, parse
from cre_brain.state.graph import _new_event_id


class EventInputError(ValueError):
    """Safe fixed-message rejection; never echo a provider payload or parse error."""


@dataclass(frozen=True)
class Sanitizer:
    # Supplied by the trusted secret provisioner, never read from auth.json/env.
    secrets: tuple[str, ...] = ()

    def text(self, value: str) -> str:
        if value.lstrip().startswith(("{", "[", '"')):
            try:
                wrapper = parse('{"value":' + value + "}")
                if set(wrapper) != {"value"}:
                    return "[REDACTED]"
                embedded = wrapper["value"]
            except (ValueError, RecursionError):
                return "[REDACTED]"
            else:
                clean = self.scrub(embedded)
                if clean != embedded:
                    value = canonical(clean)
        for secret in sorted(set(self.secrets), key=len, reverse=True):
            if secret:
                value = value.replace(secret, "[REDACTED]")
                for ensure_ascii in (True, False):
                    escaped = json.dumps(secret, ensure_ascii=ensure_ascii)[1:-1]
                    if escaped != secret:
                        value = value.replace(escaped, "[REDACTED]")
        value = re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value)
        value = re.sub(r"\b(?:sk|pk|ghp|github_pat)[-_][A-Za-z0-9_-]{8,}", "[REDACTED]", value)
        value = re.sub(
            r"""(?ix)
            ((?:["']?(?:api[_-]?key|password|secret|authorization|credential|token|
                access[_-]?token)["']?)\s*[:=]\s*)
            (?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;}\]]+)
            """,
            r'\1"[REDACTED]"',
            value,
        )
        return value

    def scrub(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.scrub(item) for item in value]
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                clean_key = self.text(key)
                if clean_key in result:
                    raise EventInputError("Sanitized event keys collide")
                sensitive = re.search(
                    r"(?i)(secret|password|api[_-]?key|authorization|credential|^token$|access_token)",
                    key,
                )
                result[clean_key] = "[REDACTED]" if sensitive else self.scrub(child)
            return result
        return value


class Usage(Boundary):
    input_tokens: int = Field(strict=True, ge=0, le=1000000000)
    cached_input_tokens: int = Field(default=0, strict=True, ge=0, le=1000000000)
    output_tokens: int = Field(strict=True, ge=0, le=1000000000)


@dataclass(frozen=True)
class Frame:
    raw: dict[str, Any]  # sanitized provider structure, not byte-exact source JSONL
    events: tuple[AgentEvent, ...]


class Normalizer:
    def __init__(self, seg: SegmentSpec, ws: Workspace, sanitizer: Sanitizer) -> None:
        self.seg = SegmentSpec.model_validate(seg.model_dump())
        self.ws = Workspace.model_validate(ws.model_dump())
        self.sanitizer = sanitizer
        self.session_id = seg.resume_session_id
        self.local_seq = 0
        self.turns = 0
        self.tokens = 0
        self.turn_open = False
        self.thread_seen = False
        self.completed_items: set[str] = set()

    def make(self, kind: AgentEventKind, payload: dict[str, Any]) -> AgentEvent:
        self.local_seq += 1
        now = datetime.now(UTC)
        clean = self.sanitizer.scrub(parse(canonical(payload)))
        return AgentEvent(
            event_id=_new_event_id(now),
            task_id=self.seg.task_id,
            seq=None,
            origin=(self.ws.box.box_id, self.seg.segment_no, self.local_seq),
            ts=now,
            source="system"
            if kind in {"segment_start", "segment_end", "error", "budget"}
            else "agent",
            kind=kind,
            cause_id=None,
            release_id=self.seg.release_id,
            runner="codex",
            payload=clean,
        )

    def feed(self, line: bytes) -> Frame:
        try:
            if len(line) > MAX_BYTES or not line.endswith(b"\n") or b"\n" in line[:-1]:
                raise ValueError
            body = parse(line.decode("utf-8"))
            event_type = body.get("type")
            if not isinstance(event_type, str) or len(event_type) > 128:
                raise ValueError
            clean = self.sanitizer.scrub(body)
            # Validate sanitized representation too: expansion may exceed bounds.
            parse(canonical(clean))
            converted: list[AgentEvent] = []
            unsupported = False
            if event_type == "thread.started":
                session = TypeAdapter(ID).validate_python(body.get("thread_id"))
                if self.thread_seen or self.session_id not in {None, session}:
                    raise ValueError
                if self.sanitizer.text(session) != session:
                    raise ValueError
                self.session_id = session
                self.thread_seen = True
                converted.append(self.make("resume", {"session_id": session}))
            elif event_type == "turn.started":
                if self.session_id is None or self.turn_open:
                    raise ValueError
                self.turn_open = True
            elif event_type == "turn.completed":
                if not self.turn_open or self.session_id is None:
                    raise ValueError
                usage = Usage.model_validate(body.get("usage"))
                if usage.cached_input_tokens > usage.input_tokens:
                    raise ValueError
                self.turn_open = False
                self.turns += 1
                total = usage.input_tokens + usage.output_tokens
                self.tokens += total
                converted.append(
                    self.make(
                        "usage",
                        {
                            **usage.model_dump(),
                            "host_tokens": total,
                            "session_id": self.session_id,
                            "turn": self.turns,
                        },
                    )
                )
            elif event_type in {"error", "turn.failed"}:
                converted.append(self.make("error", {"category": "provider_error"}))
            elif event_type in {"item.started", "item.updated", "item.completed"}:
                item = clean.get("item")
                if not isinstance(item, dict) or not isinstance(item.get("type"), str):
                    raise ValueError
                item_type = item["type"]
                identity = TypeAdapter(ID).validate_python(item.get("id"))
                unsupported = item_type not in {"agent_message", "reasoning", "mcp_tool_call"}
                if event_type == "item.completed":
                    if identity in self.completed_items:
                        raise ValueError
                    self.completed_items.add(identity)
                    if item_type == "agent_message":
                        if not isinstance(item.get("text"), str):
                            raise ValueError
                        converted.append(self.make("message", {"text": item["text"]}))
                    elif item_type == "mcp_tool_call":
                        unsupported = item.get("server") != "cre"
                        if not unsupported:
                            tool = TypeAdapter(ID).validate_python(item.get("tool"))
                            arguments = item.get("arguments")
                            if isinstance(arguments, str):
                                arguments = parse(arguments)
                            if not isinstance(arguments, dict):
                                raise ValueError
                            converted.append(
                                self.make(
                                    "tool_call",
                                    {
                                        "tool": tool,
                                        "arguments": arguments,
                                        "call_id": identity,
                                    },
                                )
                            )
                            converted.append(
                                self.make(
                                    "tool_result",
                                    {
                                        "tool": tool,
                                        "call_id": identity,
                                        "result": item.get("result"),
                                        "error": item.get("error"),
                                        "status": item.get("status"),
                                    },
                                )
                            )
            else:
                unsupported = True
            raw_event = self.make("runner_raw", {"event": clean, "unsupported": unsupported})
            return Frame(clean, (*converted, raw_event))
        except (ValueError, TypeError, RecursionError, UnicodeError):
            raise EventInputError("Invalid or oversized provider JSONL event") from None
