"""Canonical finalization seam; implementations must invoke all applicable gates.

The scaffold intentionally supplies no permissive finalizer or gate fallback.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from cre_brain.domain.base import TenantScope

DeliverableT = TypeVar("DeliverableT", bound=BaseModel, contravariant=True)
ResultT = TypeVar("ResultT", bound=BaseModel, covariant=True)


class DeliverableFinalizer(Protocol[DeliverableT, ResultT]):
    def finalize(self, deliverable: DeliverableT, *, scope: TenantScope) -> ResultT: ...
