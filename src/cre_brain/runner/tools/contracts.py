"""Small tool requests and host-only authenticated composition contracts.

Providers are injected by the host, never loaded from tool arguments or a deal file.
"""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cre_brain.domain import Deliverable, Fact, GateResult
from cre_brain.domain.base import TenantScope
from cre_brain.excel.models import TemplateMap
from cre_brain.rules.models import Policy

ID = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=4096)]


class Boundary(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, revalidate_instances="always"
    )


class Reference(Boundary):
    kind: Literal["fact", "assumption", "calc"]
    record_id: ID
    version: int = Field(strict=True, ge=1)
    key: ID
    unit: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_/.-]{1,64}$")]


class FactGet(Boundary):
    reference: Reference


class FactPut(Boundary):
    anchor_id: ID


class AssumptionSet(Boundary):
    key: ID
    value: Reference
    low: Reference
    high: Reference
    rationale: Text
    is_proxy: bool = True


class FinanceRun(Boundary):
    fn: ID
    args: dict[ID, Reference | list[Reference]] = Field(max_length=32)


class ExcelBuild(Boundary):
    template: ID
    calculation: ID


class ExcelRecalc(Boundary):
    artifact_id: ID


class RulesEval(Boundary):
    table: ID
    input: dict[ID, Reference] = Field(max_length=32)


class AskUser(Boundary):
    question: Text
    why: Text
    default: Reference
    affects: list[ID] = Field(max_length=64)


class Finalize(Boundary):
    deliverable_id: ID


class DraftExternal(Boundary):
    kind: Literal["email_brokers", "send_loi"]
    to: ID  # Configured recipient identity, never an address supplied by the model.
    body: Text
    deliverable_id: ID | None = None


class SendExternal(Boundary):
    draft_id: ID


class FactAnchor(Boundary):
    fact: Fact
    authority: Literal["verified_source", "authorized_user", "quarantine"]


class Artifact(Boundary):
    deliverable: Deliverable
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    extraction: bool = False


class Template(Boundary):
    path: Path
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    mapping: TemplateMap


class AuthenticatedContext(Boundary):
    scope: TenantScope
    task_id: ID
    deal_id: ID
    role: Literal["lead", "user", "extraction", "verifier", "classifier", "reflection"]
    session_id: ID
    release_id: ID
    started_at: datetime


class InputProvider(Protocol):
    def fact(self, context: AuthenticatedContext, identity: str) -> FactAnchor | None: ...
    def artifact(self, context: AuthenticatedContext, identity: str) -> Artifact | None: ...
    def template(self, context: AuthenticatedContext, identity: str) -> Template | None: ...
    def rule_policy(self, context: AuthenticatedContext, table: str) -> Policy | None: ...


class GateProvider(Protocol):
    """A host-bound GateService adapter; no caller PASS/report is consumed."""

    scope: TenantScope

    def check(self, name: str, deliverable: Deliverable) -> GateResult: ...


class ExternalConnector(Protocol):
    """Configured host connector must implement durable idempotency by key.

    The host allowlists recipient IDs and pins the connector to this tenant.
    """

    scope: TenantScope
    allowed_recipients: frozenset[str]

    def send(self, *, recipient_id: str, body: str, idempotency_key: str) -> str: ...
