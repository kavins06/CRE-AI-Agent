"""Shared tenant boundary; concrete fact/event/deliverable schemas belong in domain."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class TenantScope(BaseModel):
    """Scope obtained from trusted authentication, never from an untrusted payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: Identifier
    firm_id: Identifier
