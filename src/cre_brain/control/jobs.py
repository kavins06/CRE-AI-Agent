"""Durable helper lifecycle over canonical jobs, with host-only reconciliation.

No provider is called here. Authentication, receipt verification, and canonical
RunnerState reservation/recovery belong to trusted composition code.
"""

from datetime import datetime, timedelta
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, TypeAdapter, model_validator
from sqlalchemy import Connection, Engine, and_, select
from sqlalchemy.sql.elements import ColumnElement

from cre_brain.domain.base import TenantScope
from cre_brain.runner.orchestration.signals import HostSignal
from cre_brain.runner.tools.contracts import ID, Boundary
from cre_brain.state.schema import jobs
from cre_brain.state.store import StateConflict, lock_append, tenant_filter

Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
Revision = Annotated[int, Field(strict=True, ge=1, le=2147483647)]
UnknownPhase = Literal["creation_unknown", "start_unknown", "worker_unknown"]
Status = Literal[
    "ready",
    "creation_unknown",
    "start_unknown",
    "worker_unknown",
    "running",
    "completed",
    "stopped",
    "failed",
]
FINAL = frozenset({"completed", "stopped", "failed"})


def _aware(now: datetime) -> None:
    if now.utcoffset() is None:
        raise ValueError("Host timestamp must be timezone-aware")


class JobIdentity(Boundary):
    """Immutable host assertion; request hash covers the full runtime request."""

    scope: TenantScope
    task_id: ID
    segment_no: int = Field(strict=True, ge=0, le=2147483647)
    deal_id: ID
    release_id: ID
    box_id: ID
    runtime: ID
    request_id: ID
    request_sha256: Digest


class HostReceipt(Boundary):
    """Already verified by trusted host code, never parsed from model/deal input.

    not_started must prove no creation or launch remains in flight. A receipt
    cannot itself reconcile the separate canonical event/usage reservations.
    claim_revision is the durable claim generation verified by the host, not
    the current outer compare-and-swap revision supplied during reconciliation.
    """

    identity: JobIdentity
    receipt_id: ID
    claim_revision: Revision
    owner_id: ID
    observed_at: datetime
    outcome: Literal["not_started", "created", "running", "completed", "stopped", "failed"]
    session_id: ID | None = None
    lease_until: datetime | None = None

    @model_validator(mode="after")
    def complete(self) -> Self:
        _aware(self.observed_at)
        if self.outcome in {"running", "completed"} and self.session_id is None:
            raise ValueError("Verified runtime outcome requires a session binding")
        if self.outcome in {"not_started", "created"} and self.session_id is not None:
            raise ValueError("Pre-launch outcome cannot bind a session")
        if self.outcome == "running":
            if self.lease_until is None:
                raise ValueError("Running receipt requires verified ownership expiry")
            _aware(self.lease_until)
            if not self.observed_at < self.lease_until <= self.observed_at + timedelta(days=1):
                raise ValueError("Verified ownership expiry is outside bounds")
        elif self.lease_until is not None:
            raise ValueError("Only running receipts can assert healthy ownership")
        return self


class Job(Boundary):
    identity: JobIdentity
    owner_id: ID
    status: Status
    revision: Revision
    claim_revision: Revision
    session_id: ID | None = None
    receipt: HostReceipt | None = None

    @model_validator(mode="after")
    def binding(self) -> Self:
        if self.claim_revision > self.revision:
            raise ValueError("Claim generation cannot exceed the current job revision")
        if self.receipt is not None and (
            self.receipt.identity != self.identity
            or self.receipt.claim_revision != self.claim_revision
        ):
            raise ValueError("Job receipt does not match its immutable binding")
        if self.status in FINAL and (
            self.receipt is None
            or self.receipt.outcome != self.status
            or self.receipt.owner_id != self.owner_id
            or self.receipt.session_id != self.session_id
        ):
            raise ValueError("Terminal job requires a matching verified host outcome")
        if self.status == "ready" and (
            self.receipt is None
            or self.receipt.outcome != "not_started"
            or self.session_id is not None
        ):
            raise ValueError("Retry readiness requires a verified no-launch outcome")
        if self.status == "running" and (
            self.receipt is None
            or self.receipt.outcome != "running"
            or self.receipt.session_id != self.session_id
            or self.receipt.owner_id != self.owner_id
        ):
            raise ValueError("Healthy ownership requires a verified host receipt")
        return self


class Claim(Boundary):
    job: Job
    acquired: bool
    signal: HostSignal | None = None


class JobStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _where(identity: JobIdentity) -> ColumnElement[bool]:
        return and_(
            tenant_filter(jobs, identity.scope),
            jobs.c.task_id == identity.task_id,
            jobs.c.segment_no == identity.segment_no,
        )

    def _read(self, connection: Connection, identity: JobIdentity) -> Job | None:
        row = connection.execute(
            select(jobs.c.payload, jobs.c.status).where(self._where(identity))
        ).one_or_none()
        if row is None:
            return None
        job = Job.model_validate(row.payload)
        if job.identity != identity or job.status != row.status:
            raise StateConflict("Job immutable identity or canonical status conflicts")
        return job

    def _write(self, connection: Connection, job: Job, *, new: bool = False) -> None:
        job = Job.model_validate(job.model_dump())
        values = dict(status=job.status, payload=job.model_dump(mode="json"))
        if new:
            connection.execute(
                jobs.insert().values(
                    user_id=job.identity.scope.user_id,
                    firm_id=job.identity.scope.firm_id,
                    task_id=job.identity.task_id,
                    segment_no=job.identity.segment_no,
                    **values,
                )
            )
        else:
            connection.execute(jobs.update().where(self._where(job.identity)).values(**values))

    @staticmethod
    def _lock(connection: Connection, identity: JobIdentity) -> None:
        lock_append(connection, identity.scope, ("jobs", identity.task_id))

    def get(self, identity: JobIdentity) -> Job | None:
        identity = JobIdentity.model_validate(identity.model_dump())
        with self.engine.connect() as connection:
            return self._read(connection, identity)

    def claim(self, identity: JobIdentity, *, owner_id: str, now: datetime) -> Claim:
        identity = JobIdentity.model_validate(identity.model_dump())
        _aware(now)
        owner_id = TypeAdapter(ID).validate_python(owner_id)
        with self.engine.begin() as connection:
            self._lock(connection, identity)
            job = self._read(connection, identity)
            if job is None or job.status == "ready":
                job = Job(
                    identity=identity,
                    owner_id=owner_id,
                    status="creation_unknown",
                    revision=1 if job is None else job.revision + 1,
                    claim_revision=1 if job is None else job.revision + 1,
                )
                self._write(connection, job, new=job.revision == 1)
                return Claim(job=job, acquired=True)
            if job.status == "running":
                assert job.receipt is not None and job.receipt.lease_until is not None
                if now >= job.receipt.lease_until:
                    job = Job.model_validate(
                        job.model_dump()
                        | {
                            "status": "worker_unknown",
                            "revision": job.revision + 1,
                        }
                    )
                    self._write(connection, job)
            signal = (
                None
                if job.status in FINAL or job.status == "running"
                else HostSignal(
                    actions=("recover",),
                    reason="unknown_outcome",
                )
            )
            return Claim(job=job, acquired=False, signal=signal)

    def mark_unknown(
        self,
        identity: JobIdentity,
        *,
        owner_id: str,
        revision: int,
        phase: UnknownPhase,
    ) -> Job:
        identity = JobIdentity.model_validate(identity.model_dump())
        revision = TypeAdapter(Revision).validate_python(revision)
        phase = TypeAdapter(UnknownPhase).validate_python(phase)
        owner_id = TypeAdapter(ID).validate_python(owner_id)
        with self.engine.begin() as connection:
            self._lock(connection, identity)
            job = self._read(connection, identity)
            if (
                job is None
                or job.status in FINAL
                or job.status == "ready"
                or job.owner_id != owner_id
                or job.revision != revision
            ):
                raise StateConflict("Unknown outcome requires current job ownership and revision")
            updated = Job.model_validate(
                job.model_dump()
                | {
                    "status": phase,
                    "revision": job.revision + 1,
                }
            )
            self._write(connection, updated)
            return updated

    def reconcile(self, receipt: HostReceipt, *, revision: int) -> Job:
        receipt = HostReceipt.model_validate(receipt.model_dump())
        revision = TypeAdapter(Revision).validate_python(revision)
        with self.engine.begin() as connection:
            self._lock(connection, receipt.identity)
            job = self._read(connection, receipt.identity)
            if job is None:
                raise StateConflict("Reconciliation requires an existing durable claim")
            if receipt.claim_revision != job.claim_revision:
                raise StateConflict("Verified receipt belongs to a different claim generation")
            if job.receipt is not None and job.receipt.receipt_id == receipt.receipt_id:
                if job.receipt != receipt:
                    raise StateConflict("Verified receipt identity conflicts")
                if (
                    job.status == job.receipt.outcome
                    or (job.status == "ready" and receipt.outcome == "not_started")
                    or (job.status == "start_unknown" and receipt.outcome == "created")
                ):
                    return job
            if job.revision != revision or job.status in FINAL:
                raise StateConflict("Reconciliation requires current nonfinal job revision")
            if job.receipt is not None and receipt.observed_at <= job.receipt.observed_at:
                raise StateConflict("Reconciliation requires newer verified host evidence")
            if job.session_id is not None and job.session_id != receipt.session_id:
                raise StateConflict("Verified session binding is immutable")
            if receipt.outcome == "not_started" and job.status not in {
                "creation_unknown",
                "start_unknown",
                "worker_unknown",
            }:
                raise StateConflict("Retry requires trusted reconciliation of an unknown outcome")
            status: Status = (
                "ready"
                if receipt.outcome == "not_started"
                else "start_unknown"
                if receipt.outcome == "created"
                else receipt.outcome
            )
            updated = Job(
                identity=job.identity,
                owner_id=receipt.owner_id,
                status=status,
                revision=job.revision + 1,
                claim_revision=job.claim_revision,
                session_id=receipt.session_id,
                receipt=receipt,
            )
            self._write(connection, updated)
            return updated
