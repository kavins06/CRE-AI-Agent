"""Read-only admission helper delegating reservation/recovery to RunnerState.

The base adapter lacks these accounting hooks: absence is a recovery signal,
never permission to count only emitted usage or launch another segment.
"""

from typing import Literal, Protocol

from pydantic import Field

from cre_brain.domain import AgentEvent
from cre_brain.runner.normalizer import Usage
from cre_brain.runner.orchestration.signals import HostSignal
from cre_brain.runner.policy import Limits
from cre_brain.runner.state_adapter import RunnerState
from cre_brain.runner.tools.contracts import Boundary
from cre_brain.sandbox.base import SandboxError
from cre_brain.state.store import StateConflict


class CanonicalAccounting(Protocol):
    """Trusted state_adapter hooks; both receive the SAME locked canonical history.

    token_commitment includes spent AND pending reservations across the task.
    require_recovered validates session/usage bindings and unknown outcomes.
    This seam has no implementation or default substitute in this slice.
    """

    def require_recovered(self, history: list[AgentEvent]) -> None: ...
    def token_commitment(self, history: list[AgentEvent]) -> int: ...


class BudgetRequest(Boundary):
    requested_tokens: int = Field(strict=True, ge=0, le=100000000)


class BudgetSnapshot(Boundary):
    status: Literal["known", "incomplete", "unavailable"]
    spent: int | None = Field(default=None, strict=True, ge=0, le=9223372036854775807)
    reserved: int | None = Field(default=None, strict=True, ge=0, le=9223372036854775807)
    commitment: int | None = Field(default=None, strict=True, ge=0, le=9223372036854775807)
    signal: HostSignal | None = None


def _spent(history: list[AgentEvent]) -> int:
    tokens = 0
    for event in history:
        if "host_tokens" not in event.payload:
            if event.kind == "usage" and event.payload.get("tools_call") is not True:
                raise ValueError("Usage accounting is incomplete")
            continue
        value = event.payload["host_tokens"]
        if event.kind != "usage" or type(value) is not int or not 0 <= value <= 2000000000:
            raise ValueError("Invalid canonical host usage")
        if any(
            k in event.payload for k in ("input_tokens", "output_tokens", "cached_input_tokens")
        ):
            usage = Usage.model_validate(
                {
                    k: event.payload[k]
                    for k in ("input_tokens", "output_tokens", "cached_input_tokens")
                    if k in event.payload
                }
            )
            if (
                usage.cached_input_tokens > usage.input_tokens
                or usage.input_tokens + usage.output_tokens != value
            ):
                raise ValueError("Canonical host usage components conflict")
        tokens += value
    return tokens


def budget_snapshot(
    state: RunnerState,
    *,
    requested_tokens: int,
    accounting: CanonicalAccounting | None = None,
) -> BudgetSnapshot:
    """Advisory view, not an atomic reservation or authorization to launch.

    Actual admission must still call RunnerState.reserve under its transaction.
    No mutable usage counter or recovery ledger is created by this helper.
    """
    request = BudgetRequest(requested_tokens=requested_tokens)
    if accounting is None:
        return BudgetSnapshot(
            status="unavailable",
            signal=HostSignal(
                actions=("recover",),
                reason="accounting_unavailable",
            ),
        )
    with state.registry.transaction() as transaction:
        history = transaction.history()
        try:
            if len(history) > 100000:
                raise ValueError("Canonical history exceeds helper bound")
            context = state.registry.context
            if any(e.task_id != context.task_id or e.seq is None for e in history):
                raise ValueError("Usage ledger must contain committed canonical task events")
            accounting.require_recovered(history)
            spent = _spent(history)
            commitment = accounting.token_commitment(history)
            if type(commitment) is not int or commitment < spent:
                raise ValueError("Canonical commitment must include spent and pending reservations")
            # Revalidate configured policy rather than accepting a caller-supplied cap.
            cap = Limits.model_validate(state.registry.limits.model_dump()).max_tokens
            signal = None
            if commitment >= cap or request.requested_tokens > cap - commitment:
                signal = HostSignal(actions=("stop", "escalate"), reason="budget_cap")
            return BudgetSnapshot(
                status="known",
                spent=spent,
                reserved=commitment - spent,
                commitment=commitment,
                signal=signal,
            )
        except (ValueError, TypeError, SandboxError, StateConflict):
            return BudgetSnapshot(
                status="incomplete",
                signal=HostSignal(
                    actions=("recover",),
                    reason="accounting_incomplete",
                ),
            )
