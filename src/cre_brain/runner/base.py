"""Canonical runner/policy seams, parameterized by the domain models.

No runner or permission implementation is supplied by the scaffold.
"""

from collections.abc import AsyncIterator
from typing import Protocol, TypeVar

from pydantic import BaseModel

SegmentT = TypeVar("SegmentT", bound=BaseModel, contravariant=True)
WorkspaceT = TypeVar("WorkspaceT", contravariant=True)
PolicyT = TypeVar("PolicyT", contravariant=True)
EventT = TypeVar("EventT", bound=BaseModel, covariant=True)
ActionT = TypeVar("ActionT", contravariant=True)
DecisionT = TypeVar("DecisionT", covariant=True)


class Policy(Protocol[ActionT, DecisionT]):
    def check(self, action: ActionT) -> DecisionT: ...


class Runner(Protocol[SegmentT, WorkspaceT, PolicyT, EventT]):
    # An async generator returns an AsyncIterator directly, not an awaitable of one.
    def run_segment(
        self, seg: SegmentT, ws: WorkspaceT, policy: PolicyT
    ) -> AsyncIterator[EventT]: ...
