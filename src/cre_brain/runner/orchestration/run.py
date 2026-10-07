"""Bounded host composition: one claimed lead segment and checked SCREEN publication.

This module installs no runtime, parses no authority from a deal, and implements
no attach/recovery fallback. Native evidence verification is an explicit host seam.
"""

import asyncio
import hashlib
import time
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import aclosing
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, Self, runtime_checkable

from pydantic import Field, ValidationError, model_validator

from cre_brain.control.jobs import HostReceipt, Job, JobIdentity, JobStore, Revision
from cre_brain.deliverables.screen import ScreenInputs, ScreenService
from cre_brain.deliverables.screen.models import Document
from cre_brain.domain import AgentEvent, Deliverable, DeliverableKind, GateResult
from cre_brain.extraction.preparse import PreparseError, Preparser
from cre_brain.extraction.preparse.models import digest as extraction_digest
from cre_brain.extraction.quarantine import ExtractionResult, Extractor
from cre_brain.extraction.runtime import (
    ExtractionBundle,
    ExtractionCapabilities,
    ExtractionProvider,
    ExtractionRequest,
    ExtractionRuntime,
)
from cre_brain.extraction.schemas import SourceDocument
from cre_brain.gates import GateService
from cre_brain.gates.snapshot import ArtifactSnapshot
from cre_brain.runner.codex import CodexRunner
from cre_brain.runner.instructions import generate
from cre_brain.runner.orchestration.budget import budget_snapshot
from cre_brain.runner.orchestration.run_operations import (
    FaultDiagnostic,
    HostOperations,
    HostOperationUnknown,
)
from cre_brain.runner.orchestration.stuck import StuckDetector, StuckLimits, StuckState
from cre_brain.runner.policy import HostContext, Refusal
from cre_brain.runner.segment import SegmentSpec, Workspace
from cre_brain.runner.state_adapter import RunnerState, require_recovered, token_commitment
from cre_brain.runner.streaming import (
    CancellationReceipt,
    ExecutionRequest,
    InstructionBundle,
    RunningProcess,
    RuntimeCapabilities,
    StreamingAdapter,
)
from cre_brain.runner.tools.contracts import ID, Boundary, Reference
from cre_brain.runner.tools.evidence import screen_fact
from cre_brain.runner.tools.finalization import artifact_snapshot, trusted_release
from cre_brain.runner.tools.json_io import canonical
from cre_brain.runner.tools.registry import ToolRegistry
from cre_brain.runner.tools.state import ToolState
from cre_brain.sandbox.base import Box, SandboxError, SandboxProvider
from cre_brain.state import publications
from cre_brain.state.publications import PublicationReference
from cre_brain.state.store import StateConflict


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class RunInput(Boundary):
    deal: str = Field(min_length=1, max_length=4096)
    request: str = Field(min_length=1, max_length=8192)

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if (
            not Path(self.deal).is_absolute()
            or any(p in {".", ".."} for p in self.deal.split("/"))
            or not self.request.strip()
            or any(ord(c) < 32 and c not in "\n\t" for c in self.request)
            or any(ord(c) < 32 for c in self.deal)
            or len(self.request.encode()) > 16384
        ):
            raise ValueError("Use an absolute deal selector and a bounded nonempty request")
        return self


class SourcePin(Boundary):
    relative_path: str = Field(min_length=1, max_length=1024)
    source: SourceDocument
    descriptor: Document

    @model_validator(mode="after")
    def bound(self) -> Self:
        from cre_brain.extraction.preparse.files import relative_parts

        relative_parts(self.relative_path)
        if (
            self.source.document.doc_id != self.descriptor.doc_id
            or Path(self.relative_path).name != self.source.document.source_name
            or self.descriptor.filename != self.source.document.source_name
            or hashlib.sha256(self.source.document.model_dump_json().encode()).hexdigest()
            != self.source.parsed_sha256
        ):
            raise ValueError("Pin must identify the exact parsed source and descriptor")
        return self


class RunPlan(Boundary):
    """Authenticated host pins; never accepted from CLI JSON or seller files."""

    request: RunInput
    context: HostContext
    workspace: Workspace
    segment: SegmentSpec
    request_id: ID
    owner_id: ID
    sources: tuple[SourcePin, ...] = Field(min_length=1, max_length=32)
    headlines: tuple[tuple[ID, Reference], ...] = Field(max_length=16)
    capabilities: RuntimeCapabilities
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    kind: Literal["SCREEN", "UW_MODEL"] = "SCREEN"
    stuck: StuckLimits = Field(default_factory=StuckLimits)
    poll_s: float = Field(default=1, gt=0, le=5)
    cleanup_s: float = Field(default=15, ge=10, le=30)

    @model_validator(mode="after")
    def binding(self) -> Self:
        if (
            self.segment.prompt != self.request.request
            or self.segment.resume_session_id is not None
            or self.context.role != "lead"
            or self.workspace.scope != self.context.scope
            or (self.segment.task_id, self.segment.deal_id, self.segment.release_id)
            != (self.context.task_id, self.context.deal_id, self.context.release_id)
            or len({p.source.document.doc_id for p in self.sources}) != len(self.sources)
            or len({k for k, _ in self.headlines}) != len(self.headlines)
            or any(
                p.source.document.scope != self.context.scope
                or p.source.deal_id != self.context.deal_id
                for p in self.sources
            )
        ):
            raise ValueError("Plan requires exact immutable authenticated bindings")
        return self

    @property
    def identity(self) -> JobIdentity:
        return JobIdentity(
            scope=self.context.scope,
            task_id=self.context.task_id,
            segment_no=self.segment.segment_no,
            deal_id=self.context.deal_id,
            release_id=self.context.release_id,
            box_id=self.workspace.box.box_id,
            runtime="codex",
            request_id=self.request_id,
            request_sha256=digest(self.model_dump(mode="json")),
        )


class RunPublicationPin(Boundary):
    deliverable_id: ID
    version: int = Field(strict=True, ge=2)
    entries: tuple[PublicationReference, ...] = Field(min_length=1, max_length=5)


class RunResult(Boundary):
    status: Literal["ok", "refused"]
    category: ID | None = None
    reason: ID | None = None
    evidence: Literal["isolated_runtime", "synthetic_plumbing_only"] | None = None
    deliverable_ids: tuple[ID, ...] = Field(default=(), max_length=2)

    publications: tuple[RunPublicationPin, ...] = Field(default=(), max_length=2)
    diagnostic: FaultDiagnostic | None = None

    @model_validator(mode="after")
    def complete(self) -> Self:
        if self.status == "ok":
            if (
                self.category is not None
                or self.reason is not None
                or self.evidence is None
                or len(set(self.deliverable_ids)) != 2
                or tuple(pin.deliverable_id for pin in self.publications) != self.deliverable_ids
                or self.diagnostic is not None
            ):
                raise ValueError("Success requires distinct checked publications and evidence")
        elif (
            self.category is None
            or self.evidence is not None
            or self.deliverable_ids
            or self.publications
        ):
            raise ValueError("Refusal cannot imply publication or runtime evidence")
        return self


def refused(category: str, reason: str | None = None) -> RunResult:
    return RunResult(status="refused", category=category, reason=reason)


class NativeClaim(Boundary):
    """Host adapter pins this before stage/start; receipts retain THIS generation."""

    identity: JobIdentity
    claim_revision: Revision
    owner_id: ID


@runtime_checkable
class ClaimBoundRuntime(StreamingAdapter, Protocol):
    @property
    def claim_binding(self) -> NativeClaim:
        """Native start/cleanup evidence must be attested against this immutable pin."""
        ...


class ReceiptVerifier(Protocol):
    async def verify(self, job: Job) -> HostReceipt:
        """Verify native outcome for THIS claim generation, session, owner and request."""
        ...


class HostControls(Protocol):
    async def nudge(self, job: Job) -> None:
        """Deliver a bounded host nudge to the claimed native session; no model authority."""
        ...


@dataclass(frozen=True)
class RunSession:
    preparser: Preparser
    extractor: Extractor
    screen: ScreenService
    runner: CodexRunner
    receipts: ReceiptVerifier
    controls: HostControls


@dataclass(frozen=True)
class RunHost:
    """Host-owned authentication and construction, never a deal/plugin loader.

    authorize does bounded authentication/local selection only: it must NOT
    provision, stage or launch any runtime. compose constructs adapters after
    claim; it must NOT start a native lead. CodexRunner owns atomic admission
    and launch. Both callbacks are trusted embedding code, not sandboxed code.
    """

    jobs: JobStore
    authorize: Callable[[RunInput], RunPlan]
    compose: Callable[[RunPlan, Job], RunSession]
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    operations: HostOperations = field(default_factory=HostOperations)


@dataclass(frozen=True)
class RunPublicationAuthority:
    """Run lifecycle restriction; generic enforcement belongs to finalization."""

    host: RunHost
    native: NativeClaim
    context: HostContext

    def authorize(self, registry: ToolRegistry, state: ToolState) -> None:
        job = self.host.jobs.get(self.native.identity)
        if (
            registry.engine is not self.host.jobs.engine
            or registry.context != self.context
            or state.context != self.context
            or job is None
            or job.status != "completed"
            or job.owner_id != self.native.owner_id
            or job.claim_revision != self.native.claim_revision
            or self.host.operations.recovery_required(self.native.identity)
        ):
            raise Refusal("gate_failure", "Host lifecycle authorization is unavailable")
        require_recovered(state.history(task_only=False))


def _registry_pin(
    session: RunSession, plan: RunPlan, host: RunHost, registry: ToolRegistry
) -> None:
    if (
        session.runner.registry is not registry
        or session.extractor.registry is not registry
        or session.screen.registry is not registry
        or registry.context != plan.context
        or registry.engine is not host.jobs.engine
    ):
        raise Refusal("binding_mismatch", "Run host registry bindings changed")


def _intake_pin(session: RunSession, plan: RunPlan) -> None:
    if configuration_digest(session, plan) != plan.configuration_sha256:
        raise Refusal("binding_mismatch", "Run configuration binding changed")
    _source_bytes(session, plan)


class GuardedRuntime:
    """Recheck after capability/staging awaits and immediately before native start.

    The trusted adapter still owns atomic native configuration/launch evidence;
    this wrapper does not defend against replacing all trusted host code.
    """

    def __init__(
        self, inner: ClaimBoundRuntime, session: RunSession, plan: RunPlan, host: RunHost, job: Job
    ) -> None:
        self.inner, self.session, self.plan, self.host, self.job = inner, session, plan, host, job
        self.provider: SandboxProvider = inner.provider
        self.registry: ToolRegistry = inner.registry
        self.failure: Refusal | None = None
        self.fault: FaultDiagnostic | None = None
        self.lead_task: asyncio.Task[None] | None = None

    @property
    def claim_binding(self) -> NativeClaim:
        return self.inner.claim_binding

    def check_identity(self) -> None:
        try:
            _registry_pin(self.session, self.plan, self.host, self.registry)
            if self.inner.registry is not self.registry or self.inner.provider is not self.provider:
                raise Refusal("binding_mismatch", "Runtime transport identity changed")
        except Refusal as error:
            self.failure = error
            raise

    def check(
        self,
        *,
        active: bool = False,
        extraction_batch: str | None = None,
        observed_extraction: asyncio.Task[Any] | None = None,
    ) -> None:
        try:
            self.check_identity()
            # Source pins are checked before _validate reads any tenant lifecycle evidence.
            _source_bytes(self.session, self.plan)
            _validate(
                self.session,
                self.plan,
                self.host,
                self.job,
                active=active,
                evidence=False,
                extraction_batch=extraction_batch,
                observed_task=observed_extraction or self.lead_task,
            )
        except Refusal as error:
            self.failure = error
            raise
        except Exception as error:
            self.capture(error)
            raise

    def capture(self, error: Exception, *, stage: str = "host") -> None:
        if not isinstance(error, (SandboxError, Refusal, ValidationError, PreparseError)):
            self.fault = self.host.operations.record_fault(error, stage=stage)

    async def checked_call[T](self, operation: Coroutine[Any, Any, T]) -> T:
        try:
            return await operation
        except Exception as error:
            self.capture(error)
            raise

    async def capabilities(self, box: Box) -> RuntimeCapabilities:
        self.check()
        try:
            caps = await self.inner.capabilities(box)
        except Exception as error:
            if not isinstance(error, (SandboxError, Refusal, ValidationError)):
                self.fault = self.host.operations.record_fault(error)
            raise
        self.check()
        if caps != self.plan.capabilities:
            self.failure = Refusal("binding_mismatch", "Runtime capabilities changed")
            raise self.failure
        return caps

    async def stage(self, box: Box, bundle: InstructionBundle) -> None:
        self.check(active=True)
        expected = generate(
            self.session.runner.brain_root,
            self.plan.segment,
            self.registry,
            self.session.runner.model_provider,
            firm_summary=self.session.runner.firm_summary,
            user_memory=self.session.runner.user_memory,
        )
        if box != self.plan.workspace.box or bundle != expected:
            self.failure = Refusal("binding_mismatch", "Trusted stage identity changed")
            raise self.failure
        await self.checked_call(self.inner.stage(box, bundle))
        self.check(active=True)

    async def start(self, box: Box, request: ExecutionRequest) -> RunningProcess:
        self.check(active=True)
        if box != self.plan.workspace.box or request.segment != self.plan.segment:
            self.failure = Refusal("binding_mismatch", "Native request identity changed")
            raise self.failure
        try:
            process = await self.inner.start(box, request)
            return GuardedProcess(process, self, "lead")
        except Exception as error:
            if not isinstance(error, (SandboxError, Refusal, ValidationError)):
                self.fault = self.host.operations.record_fault(error)
            raise


class GuardedProcess:
    """Capture safe process fault diagnostics before existing runtime handlers erase them."""

    def __init__(self, inner: RunningProcess, guard: GuardedRuntime, role: str) -> None:
        self.inner, self.guard, self.role = inner, guard, role

    async def stdout(self) -> AsyncIterator[bytes]:
        try:
            async for line in self.inner.stdout():
                self.guard.check_identity()
                yield line
        except Exception as error:
            self.guard.capture(error, stage=f"{self.role}.stdout")
            raise

    async def wait(self) -> int:
        try:
            result = await self.inner.wait()
            self.guard.check_identity()
            return result
        except Exception as error:
            self.guard.capture(error, stage=f"{self.role}.wait")
            raise

    async def cancel(self) -> CancellationReceipt:
        try:
            receipt = await self.inner.cancel()
            try:
                self.guard.check_identity()
            except Refusal:
                # Preserve native stop/accounting evidence after binding refusal.
                pass
            return receipt
        except Exception as error:
            self.guard.capture(error, stage=f"{self.role}.cancel")
            raise


class GuardedExtractionRuntime:
    """Revalidate host pins across quarantine awaits without replacing its accounting."""

    def __init__(self, inner: ExtractionRuntime, guard: GuardedRuntime) -> None:
        self.inner, self.guard = inner, guard
        self.batch_task: asyncio.Task[Any] | None = None
        self.provider: ExtractionProvider = inner.provider
        sources = tuple(pin.source for pin in guard.plan.sources)
        bundles = tuple(guard.session.extractor._bundle(source) for source in sources)
        self.bundles = {bundle.parsed_sha256: bundle for bundle in bundles}
        context = guard.plan.context
        self.batch = "batch-" + extraction_digest(
            (
                context.scope.model_dump(),
                context.deal_id,
                context.release_id,
                [source.model_dump(mode="json") for source in sources],
                [bundle.sha256 for bundle in bundles],
                guard.session.extractor.limits.model_dump(),
            )
        )

    def check(self, box: Box, parsed: str, bundle: str) -> None:
        self.guard.check(extraction_batch=self.batch, observed_extraction=self.batch_task)
        expected = self.bundles.get(parsed)
        if (
            self.inner.provider is not self.provider
            or box.kind != "extractor"
            or box.user_id != self.guard.plan.context.scope.user_id
            or expected is None
            or expected.sha256 != bundle
        ):
            raise Refusal("binding_mismatch", "Extraction stage binding changed")

    async def extract(self, identities: tuple[str, ...]) -> ExtractionResult:
        """The host owns this exact batch task, including quarantine's child drain."""
        self.batch_task = asyncio.current_task()
        try:
            return await self.guard.session.extractor.extract(identities)
        finally:
            self.batch_task = None

    async def stage(self, box: Box, bundle: ExtractionBundle) -> None:
        self.check(box, bundle.parsed_sha256, bundle.sha256)
        if bundle != self.bundles[bundle.parsed_sha256]:
            raise Refusal("binding_mismatch", "Extraction instructions changed")
        await self.guard.checked_call(self.inner.stage(box, bundle))
        self.check(box, bundle.parsed_sha256, bundle.sha256)

    async def capabilities(self, box: Box, bundle: ExtractionBundle) -> ExtractionCapabilities:
        self.check(box, bundle.parsed_sha256, bundle.sha256)
        caps = await self.guard.checked_call(self.inner.capabilities(box, bundle))
        self.check(box, bundle.parsed_sha256, bundle.sha256)
        return caps

    async def start(self, box: Box, request: ExtractionRequest) -> RunningProcess:
        self.check(box, request.parsed_sha256, request.bundle_sha256)
        process = await self.guard.checked_call(self.inner.start(box, request))
        return GuardedProcess(process, self.guard, "extraction")


def _bind_session(session: RunSession, plan: RunPlan, host: RunHost, job: Job) -> GuardedRuntime:
    registry = session.runner.registry
    native = NativeClaim(
        identity=job.identity, owner_id=job.owner_id, claim_revision=job.claim_revision
    )
    if registry.publication_authority is None:
        registry.bind_publication_authority(RunPublicationAuthority(host, native, plan.context))
    runtime = session.runner.runtime
    if isinstance(runtime, GuardedRuntime):
        return runtime
    if not isinstance(runtime, ClaimBoundRuntime):
        raise Refusal("missing_runtime", "Runtime must bind the native claim")
    guarded = GuardedRuntime(runtime, session, plan, host, job)
    session.runner.runtime = guarded
    if session.extractor.runtime is None:
        raise Refusal("missing_runtime", "Extraction requires trusted transport")
    session.extractor.runtime = GuardedExtractionRuntime(session.extractor.runtime, guarded)
    return guarded


class RunGateService(GateService):
    """Additional lifecycle barrier, delegating every verdict to existing gates.

    Host composition must install this on the SAME registry before exposing tools.
    A native lead cannot publish while its durable outcome/usage remains unknown.
    No gate list, evidence authority, or blocking assertion is replaced.
    """

    def __init__(
        self, source: GateService, *, jobs: JobStore, job: Job, context: HostContext
    ) -> None:
        super().__init__(
            source.engine,
            scope=source.scope,
            settings=source.settings,
            inputs=source.inputs,
            scratch=source.scratch,
            as_of=source.state.as_of,
        )
        self.jobs = jobs
        self.identity = JobIdentity.model_validate(job.identity.model_dump())
        self.claim_revision = job.claim_revision
        self.context = HostContext.model_validate(context.model_dump())

    def check_bytes(
        self, gate: str, deliverable: Deliverable, snapshot: ArtifactSnapshot
    ) -> GateResult:
        job = self.jobs.get(self.identity)
        if job is None or job.status != "completed" or job.claim_revision != self.claim_revision:
            raise Refusal(
                "recovery_unavailable", "Publication requires reconciled native completion"
            )
        with self.engine.connect() as connection:
            require_recovered(ToolState(connection, self.context).history(task_only=False))
        return super().check_bytes(gate, deliverable, snapshot)


class _Accounting:
    require_recovered = staticmethod(require_recovered)
    token_commitment = staticmethod(token_commitment)


def configuration_digest(session: RunSession, plan: RunPlan) -> str:
    """Exact execution config, generated instructions and host policy; no model defaults."""
    registry = session.runner.registry
    bundle = generate(
        session.runner.brain_root,
        plan.segment,
        registry,
        session.runner.model_provider,
        firm_summary=session.runner.firm_summary,
        user_memory=session.runner.user_memory,
    )
    return digest(
        {
            "context": registry.context.model_dump(mode="json"),
            "workspace": str(registry.workspace),
            "settings": registry.settings.model_dump(mode="json"),
            "limits": registry.limits.model_dump(mode="json"),
            "instructions": bundle.sha256,
            "model_provider": session.runner.model_provider,
            "raw_root": str(session.preparser.raw_root),
            "parsed_root": str(session.preparser.output_root),
            "parse_limits": session.preparser.limits.model_dump(mode="json"),
            "extraction_limits": session.extractor.limits.model_dump(mode="json"),
            "extraction_image": session.extractor.image,
            "scratch": str(session.extractor.scratch),
            "extraction_model_provider": session.extractor.model_provider,
            "allow_synthetic": session.extractor.allow_synthetic,
            "buy_box": session.screen.buy_box.model_dump(mode="json"),
            "risk": registry.risk_policy.model_dump(mode="json") if registry.risk_policy else None,
            "gates": registry.gates.settings.model_dump(mode="json")
            if isinstance(registry.gates, GateService)
            else None,
            "gate_as_of": registry.gates.state.as_of.isoformat()
            if isinstance(registry.gates, GateService)
            else None,
            "gate_scratch": str(registry.gates.scratch)
            if isinstance(registry.gates, GateService)
            else None,
        }
    )


def _validate(
    session: RunSession,
    plan: RunPlan,
    host: RunHost,
    job: Job,
    *,
    active: bool = False,
    evidence: bool = True,
    extraction_batch: str | None = None,
    observed_task: asyncio.Task[Any] | None = None,
) -> None:
    registry = session.runner.registry
    try:
        RunnerState(registry).validate(plan.segment, plan.workspace, plan.context)
    except SandboxError:
        raise Refusal(
            "binding_mismatch", "Runtime requires the exact authenticated host scope"
        ) from None
    gates = registry.gates
    authority = registry.publication_authority
    actual = host.jobs.get(job.identity)
    runtime = session.runner.runtime
    if runtime is None or not isinstance(runtime, ClaimBoundRuntime):
        raise Refusal("missing_runtime", "Host runtime must pin its native claim generation")
    native = NativeClaim.model_validate(runtime.claim_binding.model_dump())
    if (
        not isinstance(session.runner, CodexRunner)
        or actual is None
        or actual.owner_id != job.owner_id
        or actual.claim_revision != job.claim_revision
        or actual.status not in {"creation_unknown", "start_unknown", "completed"}
        or host.operations.recovery_required(job.identity, observed_task=observed_task)
        or not isinstance(authority, RunPublicationAuthority)
        or authority.native != native
        or authority.context != plan.context
        or authority.host.jobs is not host.jobs
        or authority.host.operations is not host.operations
        or native
        != NativeClaim(
            identity=job.identity, owner_id=job.owner_id, claim_revision=job.claim_revision
        )
        or not isinstance(registry.inputs, ScreenInputs)
        or registry.inputs is not session.screen.inputs
        or registry.engine is not host.jobs.engine
        or session.extractor.registry is not registry
        or session.screen.registry is not registry
        or session.preparser.scope != plan.context.scope
        or (plan.capabilities.evidence == "isolated_runtime" and session.extractor.allow_synthetic)
        or configuration_digest(session, plan) != plan.configuration_sha256
        or not isinstance(gates, RunGateService)
        or gates.identity != job.identity
        or gates.claim_revision != job.claim_revision
        or gates.jobs is not host.jobs
        or gates.context != plan.context
        or gates.engine is not registry.engine
        or gates.scope != plan.context.scope
        or gates.inputs is not session.screen.authority
    ):
        raise Refusal("binding_mismatch", "Recompose exact host runtime/configuration bindings")
    if not {"price", "units", "dscr", "occupancy", "market_tier"}.issubset(dict(plan.headlines)):
        raise Refusal("unsupported_intake", "Host must supply complete canonical headline pins")
    with registry.transaction() as state:
        history = state.history(task_only=False)
        if active:
            starts = [
                e
                for e in history
                if e.runner == "codex"
                and e.kind == "segment_start"
                and e.task_id == job.identity.task_id
                and e.release_id == job.identity.release_id
                and e.origin is not None
                and e.origin[:2] == (job.identity.box_id, job.identity.segment_no)
            ]
            if len(starts) != 1 or actual is None or actual.status != "start_unknown":
                raise Refusal("binding_mismatch", "Native admission lacks its exact durable claim")
            history = [e for e in history if e not in starts]
        if extraction_batch is not None:
            starts = [
                e
                for e in history
                if e.task_id == job.identity.task_id
                and e.release_id == job.identity.release_id
                and e.payload.get("binding") == "extraction_attempt"
                and e.payload.get("phase") == "start"
                and e.payload.get("batch") == extraction_batch
            ]
            if len(starts) != 1 or actual.status != "creation_unknown":
                raise Refusal("binding_mismatch", "Extraction lacks its exact claimed reservation")
            # Only the current authenticated reservation is active; all other
            # unfinished work and cleanup markers retain canonical recovery barriers.
            history = [e for e in history if e not in starts]
        require_recovered(history)
        if evidence:
            for _, reference in plan.headlines:
                screen_fact(state, reference)


def _source_bytes(session: RunSession, plan: RunPlan) -> None:
    """Secure no-follow byte revalidation; canonical parsing already has exact host pins."""
    from cre_brain.extraction.preparse.files import read_source

    for pin in plan.sources:
        raw = read_source(
            session.preparser.raw_root,
            session.preparser._raw_identity,
            pin.relative_path,
            session.preparser.limits.max_file_bytes,
        )
        if (
            hashlib.sha256(raw).hexdigest() != pin.source.document.source_sha256
            or session.extractor.sources.document(plan.context, pin.source.document.doc_id)
            != pin.source
        ):
            raise Refusal("binding_mismatch", "Exact authenticated source bytes changed")


def _sources(session: RunSession, plan: RunPlan, *, deadline: bool = True) -> None:
    for pin in plan.sources:
        if deadline:
            with session.runner.registry.transaction() as state:
                session.runner.registry.deadline(state)
        parsed = session.preparser.parse(pin.relative_path, doc_id=pin.source.document.doc_id)
        if (
            parsed != pin.source.document
            or session.extractor.sources.document(plan.context, parsed.doc_id) != pin.source
        ):
            raise Refusal("binding_mismatch", "Exact authenticated source fingerprint changed")
        if parsed.status != "parsed":
            raise Refusal("unsupported_intake", "Source requires reviewed intake")
        if deadline:
            with session.runner.registry.transaction() as state:
                session.runner.registry.deadline(state)


def _checked_publications(session: RunSession, plan: RunPlan, result: RunResult) -> None:
    registry = session.runner.registry
    screen_identity = "screen-" + digest(
        [
            plan.context.scope.model_dump(),
            plan.context.task_id,
            plan.context.deal_id,
            plan.context.release_id,
            plan.request_id,
        ]
    )
    if (
        result.deliverable_ids != (screen_identity + ":md", screen_identity + ":json")
        or result.status != "ok"
        or len(result.deliverable_ids) != 2
        or result.evidence != plan.capabilities.evidence
    ):
        raise Refusal("recovery_unavailable", "Incomplete checked publication manifest")
    with registry.transaction() as state:
        require_recovered(state.history(task_only=False))
        for pin in result.publications:
            identity = pin.deliverable_id
            current = state.current(Deliverable, identity)
            if current is None or current.version != pin.version:
                raise Refusal(
                    "publication_changed", "Replay requires the original publication version"
                )
            _, stored = publications.load_release(
                state.connection, registry.context, identity, pin.version
            )
            if pin.entries != tuple(
                PublicationReference(**p.reference(), size=len(p.body)) for p in stored
            ):
                raise Refusal("publication_changed", "Original protected references changed")
            anchor, snapshot = artifact_snapshot(registry, state, identity, final_replay=True)
            current = state.current(Deliverable, identity)
            if current is None or current.kind != DeliverableKind.SCREEN:
                raise Refusal("untrusted_artifact", "Expected a canonical SCREEN publication")
            trusted_release(registry, state, anchor, snapshot, current)


def _publication_pins(
    session: RunSession, identities: tuple[str, ...]
) -> tuple[RunPublicationPin, ...]:
    registry = session.runner.registry
    result = []
    with registry.transaction() as state:
        for identity in identities:
            current = state.current(Deliverable, identity)
            if current is None:
                raise Refusal("untrusted_artifact", "Missing checked publication")
            anchor, snapshot = artifact_snapshot(registry, state, identity, final_replay=True)
            trusted_release(registry, state, anchor, snapshot, current)
            _, stored = publications.load_release(
                state.connection, registry.context, identity, current.version
            )
            result.append(
                RunPublicationPin(
                    deliverable_id=identity,
                    version=current.version,
                    entries=tuple(
                        PublicationReference(**p.reference(), size=len(p.body)) for p in stored
                    ),
                )
            )
    return tuple(result)


def _replay(session: RunSession, plan: RunPlan, job: Job) -> RunResult:
    with session.runner.registry.transaction() as state:
        manifests = [
            e.payload
            for e in state.history()
            if e.runner == "tools"
            and e.source == "tool"
            and e.release_id == plan.context.release_id
            and e.payload.get("binding") == "run_publications"
            and e.payload.get("identity") == plan.identity.request_sha256
        ]
    if len(manifests) != 1 or manifests[0].get("claim_revision") != job.claim_revision:
        return refused("recovery_unavailable")
    result = RunResult.model_validate(manifests[0]["result"])
    _checked_publications(session, plan, result)
    return result


async def _drain(
    task: asyncio.Task[Any], timeout: float, interruptions: list[asyncio.CancelledError]
) -> bool:
    """Hard cleanup bound; late settlement never authorizes a new launch."""
    deadline = asyncio.get_running_loop().time() + timeout
    while not task.done():
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            task.add_done_callback(lambda t: None if t.cancelled() else t.exception())
            return False
        try:
            await asyncio.wait((task,), timeout=remaining)
        except asyncio.CancelledError as error:
            interruptions.append(error)
    return True


async def _lead(session: RunSession, plan: RunPlan, host: RunHost, job: Job) -> str | None:
    wall_base, mono_base = datetime.now(UTC), time.monotonic()

    def watchdog_now() -> datetime:
        return wall_base + timedelta(seconds=time.monotonic() - mono_base)

    detector = StuckDetector(job.identity, plan.stuck, started_at=watchdog_now())
    registry = session.runner.registry
    queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=64)
    interruptions: list[asyncio.CancelledError] = []
    reason = None

    async def pump() -> None:
        # One task owns ALL generator iterations. CodexRunner's timeout context
        # and native cleanup must remain in that same task across every yield.
        async with aclosing(
            session.runner.run_segment(plan.segment, plan.workspace, plan.context)
        ) as iterator:
            async for event in iterator:
                await queue.put(event)

    producer = host.operations.own(job.identity, asyncio.create_task(pump()))
    runtime = session.runner.runtime
    if isinstance(runtime, GuardedRuntime):
        runtime.lead_task = producer
    delivery: asyncio.Task[AgentEvent] | None = None

    def checkpoint() -> None:
        _registry_pin(session, plan, host, registry)
        actual = host.jobs.get(job.identity)
        if (
            actual is None
            or actual.owner_id != job.owner_id
            or actual.claim_revision != job.claim_revision
            or actual.status != job.status
        ):
            raise Refusal("binding_mismatch", "Watchdog claim binding changed")
        with registry.transaction() as state:
            state.event(
                "tool_result",
                {
                    "binding": "run_watchdog",
                    "identity": job.identity.request_sha256,
                    "claim_revision": job.claim_revision,
                    "clock_basis": "monotonic_elapsed",
                    "checkpoint": detector.snapshot().model_dump(mode="json"),
                },
            )

    try:
        checkpoint()
        while True:
            if producer.done() and queue.empty() and delivery is None:
                producer.result()
                break
            if delivery is None:
                delivery = asyncio.create_task(queue.get())
            watched = (delivery,) if producer.done() else (delivery, producer)
            await asyncio.wait(watched, timeout=plan.poll_s, return_when=asyncio.FIRST_COMPLETED)
            now = watchdog_now()
            signal = None
            if delivery.done():
                event = delivery.result()
                delivery = None
                if event.kind == "segment_end" and event.payload.get("reason") == "budget":
                    reason = "budget_cap"
                # All committed events remain observable after a nudge. Discrete
                # repeated-call/error thresholds retain reviewed helper semantics.
                signal = detector.observe(event, now=now)
                checkpoint()
            elif producer.done() and queue.empty():
                producer.result()
                break
            if signal is None:
                signal = detector.tick(now)
            if signal:
                checkpoint()
                if "stop" in signal.actions:
                    reason = signal.reason
                    break
                _intake_pin(session, plan)
                await host.operations.call(job, session.controls.nudge(job))
                _registry_pin(session, plan, host, registry)
                _intake_pin(session, plan)
                acknowledged = watchdog_now()
                prior = detector.snapshot()
                if acknowledged < prior.clock_at:
                    raise ValueError("Host nudge acknowledgement clock regressed")
                detector = StuckDetector(
                    job.identity,
                    plan.stuck,
                    state=StuckState.model_validate(
                        prior.model_dump()
                        | {"clock_at": acknowledged, "last_progress_at": acknowledged}
                    ),
                )
                checkpoint()
    except asyncio.CancelledError as error:
        host.operations.mark_unknown(job.identity)
        interruptions.append(error)
    finally:
        if delivery is not None:
            delivery.cancel()
            await _drain(delivery, plan.cleanup_s, interruptions)
        if not producer.done():
            producer.cancel()
        settled = await _drain(producer, plan.cleanup_s, interruptions)
        if not settled or interruptions:
            host.operations.mark_unknown(job.identity)
        if interruptions:
            if settled and not producer.cancelled():
                producer.exception()  # Consume cleanup failure without losing parent cancellation.
            raise interruptions[0]
        if not settled:
            raise SandboxError("cleanup_unverified: lead consumer remains active")
        if not producer.cancelled():
            producer.result()
    return reason


async def _reconcile(session: RunSession, host: RunHost, job: Job, guard: GuardedRuntime) -> Job:
    receipt = await host.operations.call(job, session.receipts.verify(job))
    # Awaited verification can mutate trusted bindings. Recheck even stopped/failed
    # receipts before reading lifecycle evidence or committing a terminal job.
    guard.check()
    registry = session.runner.registry
    receipt = HostReceipt.model_validate(receipt.model_dump())
    if (
        receipt.identity != job.identity
        or receipt.owner_id != job.owner_id
        or receipt.claim_revision != job.claim_revision
        or receipt.outcome not in {"completed", "stopped", "failed"}
        or receipt.observed_at > host.clock()
    ):
        raise Refusal("receipt_unavailable", "Receipt does not verify this exact claim")
    with registry.transaction() as state:
        history = state.history()
        require_recovered(state.history(task_only=False))
        ends = [
            e
            for e in history
            if e.runner == "codex"
            and e.kind == "segment_end"
            and e.release_id == job.identity.release_id
            and e.origin is not None
            and e.origin[:2] == (job.identity.box_id, job.identity.segment_no)
        ]
        if (
            len(ends) != 1
            or ends[0].payload.get("usage_complete") is not True
            or ends[0].payload.get("session_id") != receipt.session_id
            or (receipt.outcome == "completed") != (ends[0].payload.get("reason") == "completed")
            or receipt.observed_at < ends[0].ts
        ):
            raise Refusal(
                "receipt_unavailable", "Native outcome conflicts with canonical lifecycle"
            )
        if receipt.session_id is not None and not any(
            e.kind == "resume"
            and e.runner == "codex"
            and e.origin is not None
            and e.origin[:2] == (job.identity.box_id, job.identity.segment_no)
            and e.release_id == job.identity.release_id
            and e.payload.get("session_id") == receipt.session_id
            for e in history
        ):
            raise Refusal("receipt_unavailable", "Native session lacks a canonical binding")
        token_commitment(
            history
        )  # Revalidate existing canonical usage, never create a second meter.
    return host.jobs.reconcile(receipt, revision=job.revision)


async def execute_run(host: RunHost, request: RunInput) -> RunResult:
    """Factory is construction-only and called ONLY after durable claim/existing completion.

    Unknown, active, stopped and failed runs require a separate trusted recovery
    integration. This bounded slice never attaches, retries, or launches a new segment.
    """
    job: Job | None = None
    owns_claim = False
    guard: GuardedRuntime | None = None
    try:
        request = RunInput.model_validate(request.model_dump())
        plan = RunPlan.model_validate(host.authorize(request).model_dump())
        if plan.request != request:
            return refused("binding_mismatch")
        if plan.kind != "SCREEN":
            return refused("unsupported_underwriting")
        claim = host.jobs.claim(plan.identity, owner_id=plan.owner_id, now=host.clock())
        owns_claim = claim.acquired
        job = claim.job
        if not claim.acquired and job.status != "completed":
            return refused("recovery_unavailable")
        session = host.compose(plan, job)
        guard = _bind_session(session, plan, host, job)
        _validate(session, plan, host, job)
        if not claim.acquired:
            _sources(session, plan, deadline=False)
            return _replay(session, plan, job)
        registry = session.runner.registry
        caps = await session.runner.ready(plan.workspace, plan.segment)
        if caps != plan.capabilities:
            return refused("binding_mismatch")
        _validate(session, plan, host, job)
        _sources(session, plan)
        admission = budget_snapshot(
            RunnerState(registry),
            requested_tokens=plan.segment.max_tokens
            + len(plan.sources) * session.extractor.limits.max_tokens,
            accounting=_Accounting(),
        )
        if admission.signal:
            return refused(
                "escalation_unavailable"
                if admission.signal.reason == "budget_cap"
                else "recovery_unavailable",
                admission.signal.reason,
            )
        with registry.transaction() as state:
            registry.deadline(state)
        _sources(session, plan)
        assert isinstance(registry.inputs, ScreenInputs)
        for pin in plan.sources:
            registry.inputs.register_document(plan.context, pin.descriptor)
        parallel = registry.settings.budget.max_parallel_extractions
        waves = (len(plan.sources) + parallel - 1) // parallel
        extraction_s = min(
            waves * session.extractor.limits.timeout_s,
            RunnerState(registry).remaining_seconds(),
        )
        if extraction_s <= 0:
            return refused("escalation_unavailable", "budget_cap")
        extraction_runtime = session.extractor.runtime
        if not isinstance(extraction_runtime, GuardedExtractionRuntime):
            raise Refusal("binding_mismatch", "Extraction observation owner changed")
        # Own the batch, including its child drain, rather than relying on
        # cooperative asyncio.timeout inside each document. Unknown outcomes stay
        # retained by the same host owner and never authorize a replacement run.
        await host.operations.call(
            job,
            extraction_runtime.extract(tuple(p.source.document.doc_id for p in plan.sources)),
            timeout_s=extraction_s,
        )
        # Intake/extraction and capabilities must still be exactly those pinned by host auth.
        _validate(session, plan, host, job)
        _sources(session, plan)
        job = host.jobs.mark_unknown(
            job.identity, owner_id=job.owner_id, revision=job.revision, phase="start_unknown"
        )
        reason = await _lead(session, plan, host, job)
        try:
            job = await _reconcile(session, host, job, guard)
        except Refusal:
            raise
        except ValueError as error:
            # Legacy receipt adapters signal unavailable evidence with ValueError.
            # Keep that refusal contract while retaining safe fault diagnostics.
            return RunResult(
                status="refused",
                category="receipt_unavailable",
                diagnostic=host.operations.record_fault(error),
            )
        except (SandboxError, TimeoutError, StateConflict):
            if guard.fault is not None:
                return RunResult(
                    status="refused", category="internal_error", diagnostic=guard.fault
                )
            return refused("receipt_unavailable")
        if guard.fault is not None:
            return RunResult(status="refused", category="internal_error", diagnostic=guard.fault)
        if job.status != "completed" or reason:
            return refused("escalation_unavailable", reason or "segment_stopped")
        _validate(session, plan, host, job)
        _sources(session, plan)
        run = session.screen.run(
            documents=tuple(p.descriptor for p in plan.sources),
            headlines=dict(plan.headlines),
            run_id=plan.request_id,
        )
        for identity in run.deliverable_ids:
            response = registry.call("finalize_deliverable", {"deliverable_id": identity})
            if response["status"] != "ok":
                return refused(str(response["category"]))
        result = RunResult(
            status="ok",
            evidence=caps.evidence,
            deliverable_ids=run.deliverable_ids,
            publications=_publication_pins(session, run.deliverable_ids),
        )
        _checked_publications(session, plan, result)
        with registry.transaction() as state:
            registry.deadline(state)
            state.event(
                "tool_result",
                {
                    "binding": "run_publications",
                    "identity": plan.identity.request_sha256,
                    "claim_revision": job.claim_revision,
                    "result": result.model_dump(mode="json"),
                },
            )
        return result
    except asyncio.CancelledError:
        # CodexRunner owns bounded native cleanup. Preserve cancellation and the
        # durable unknown job until separately verified host recovery completes.
        raise
    except Refusal as error:
        if error.category == "budget_exceeded":
            return refused("escalation_unavailable", "budget_cap")
        return refused(error.category)
    except StateConflict:
        return refused("binding_mismatch")
    except (ValidationError, PreparseError):
        return refused("invalid_input")
    except HostOperationUnknown:
        return refused("host_operation_unknown")
    except SandboxError as error:
        if guard is not None and guard.failure is not None:
            return refused(guard.failure.category)
        if guard is not None and guard.fault is not None:
            return RunResult(status="refused", category="internal_error", diagnostic=guard.fault)
        if str(error) in {
            "Canonical policy budget exhausted",
            "Canonical extraction token budget exhausted",
            "Extraction time budget exceeded",
        }:
            return refused("escalation_unavailable", "budget_cap")
        return refused("runtime_unavailable")
    except Exception as error:
        return RunResult(
            status="refused",
            category="internal_error",
            diagnostic=host.operations.record_fault(error),
        )
    finally:
        if owns_claim and job is not None:
            await host.operations.cancel_owned(job.identity)
