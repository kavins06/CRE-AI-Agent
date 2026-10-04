"""Host-owned segment and workspace boundaries; no authority comes from JSONL."""

from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from cre_brain.domain.base import TenantScope
from cre_brain.runner.tools.contracts import ID, Boundary
from cre_brain.sandbox.base import Box

DealID = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")]


class SegmentSpec(Boundary):
    task_id: ID
    deal_id: DealID
    release_id: ID
    segment_no: int = Field(strict=True, ge=0)
    prompt: str = Field(min_length=1, max_length=16384)
    resume_session_id: ID | None = None
    max_turns: int = Field(strict=True, ge=1, le=10000)
    max_tokens: int = Field(strict=True, ge=1, le=100000000)
    timeout_s: float | None = Field(default=None, gt=0, le=86400)
    max_output_bytes: int = Field(default=8388608, strict=True, ge=1024, le=16777216)
    max_events: int = Field(default=20000, strict=True, ge=1, le=100000)

    @property
    def cwd(self) -> str:
        return f"/home/agent/work/deals/{self.deal_id}"


class Workspace(Boundary):
    box: Box
    scope: TenantScope

    @model_validator(mode="after")
    def analyst_scope(self) -> Self:
        if self.box.kind != "analyst" or self.box.user_id != self.scope.user_id:
            raise ValueError("Workspace requires an analyst box in the authenticated user scope")
        return self
