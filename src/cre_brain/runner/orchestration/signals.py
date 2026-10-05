"""Instructions to a trusted host; emitting a signal executes no action."""

from typing import Literal

from pydantic import Field

from cre_brain.runner.tools.contracts import Boundary

Reason = Literal[
    "unknown_outcome",
    "repeated_call",
    "repeated_error",
    "no_progress",
    "history_bound",
    "accounting_unavailable",
    "accounting_incomplete",
    "budget_cap",
]


class HostSignal(Boundary):
    actions: tuple[Literal["nudge", "stop", "recover", "escalate"], ...] = Field(
        min_length=1, max_length=2
    )
    reason: Reason
