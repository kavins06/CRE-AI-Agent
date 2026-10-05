"""Offline regressions for the current source slice; no runtime acceptance evidence."""

import asyncio
import json
import time
from copy import copy
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from test_run_loop import environment as run_environment
from typer.main import get_command
from typer.testing import CliRunner

from cre_brain.cli import create_app, discover_plugins
from cre_brain.domain.base import TenantScope
from cre_brain.runner.normalizer import Normalizer
from cre_brain.runner.orchestration import run
from cre_brain.runner.orchestration.run_operations import HostOperations
from cre_brain.runner.orchestration.stuck import StuckLimits
from cre_brain.runner.run_commands import install_run_host
from cre_brain.runner.state_adapter import RunnerState, require_recovered
from cre_brain.runner.tools.finalization import Refusal
from cre_brain.runner.tools.state import ToolState
from cre_brain.sandbox.base import SandboxError
from cre_brain.state.events import EventStore
from cre_brain.state.schema import metadata

environment = run_environment


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["completed", "stopped", "failed"])
async def test_repair_receipt_cannot_reconcile_another_tenant_ledger(
    environment, outcome, monkeypatch
):
    host, plan, session, transport, evidence, _ = environment
    registry = session.runner.registry
    original = evidence.verify
    receipt_returned = False
    evidence_reads = []
    history = ToolState.history

    def tracked_history(state, **kwargs):
        if receipt_returned:
            evidence_reads.append(state.context)
        return history(state, **kwargs)

    monkeypatch.setattr(ToolState, "history", tracked_history)
    other = plan.context.model_copy(
        update={"scope": TenantScope(user_id="other-user", firm_id="other-firm")}
    )
    if outcome != "completed":
        # A native nonzero exit produces a metered stopped lifecycle, without a watchdog delay.
        async def nonzero():
            return 1

        transport.process.wait = nonzero

    async def switching(job):
        nonlocal receipt_returned
        receipt = await original(job)
        with registry.transaction() as state:
            history = state.history()
            state.event(
                "tool_result",
                {
                    "binding": "extraction_attempt",
                    "identity": "unresolved-own-reservation",
                    "phase": "start",
                    "reserved_tokens": 1,
                },
            )
        for event in history:
            EventStore(registry.engine).append(
                event.model_copy(update={"event_id": str(uuid4()), "seq": None}),
                scope=other.scope,
            )
        with registry.engine.connect() as connection:
            require_recovered(ToolState(connection, other).history(task_only=False))
            with pytest.raises(SandboxError):
                require_recovered(ToolState(connection, plan.context).history(task_only=False))
        registry.context = other
        receipt_returned = True
        return receipt.model_copy(update={"outcome": outcome})

    evidence.verify = switching
    try:
        result = await run.execute_run(host, plan.request)
        assert result.category == "binding_mismatch"
        assert host.jobs.get(plan.identity).status == "start_unknown"
        assert not evidence_reads, "Reject drift before reading either tenant's lifecycle evidence"
    finally:
        registry.context = plan.context


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["completed", "stopped", "failed"])
@pytest.mark.parametrize("drift", ["source", "configuration", "registry"])
async def test_repair_receipt_rechecks_pins_before_terminal_status(
    environment, outcome, drift, monkeypatch
):
    host, plan, session, transport, evidence, _ = environment
    original = evidence.verify
    receipt_returned = False
    evidence_reads = []
    history = ToolState.history

    def tracked_history(state, **kwargs):
        if receipt_returned:
            evidence_reads.append(state.context)
        return history(state, **kwargs)

    monkeypatch.setattr(ToolState, "history", tracked_history)
    if outcome != "completed":

        async def nonzero():
            return 1

        transport.process.wait = nonzero

    async def drifting(job):
        nonlocal receipt_returned
        receipt = await original(job)
        if drift == "source":
            (session.preparser.raw_root / "rent_roll.csv").write_text("rent\n101\n200\n301\n")
        elif drift == "configuration":
            role = session.runner.registry.settings.models.roles["lead"]
            session.runner.registry.settings.models.roles["lead"] = role.model_copy(
                update={"profile": "changed"}
            )
        else:
            clone = copy(session.runner.registry)
            session.runner.registry = session.extractor.registry = session.screen.registry = clone
        receipt_returned = True
        return receipt.model_copy(update={"outcome": outcome})

    evidence.verify = drifting
    result = await run.execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert host.jobs.get(plan.identity).status == "start_unknown"
    assert not evidence_reads, "Recheck source/configuration before lifecycle evidence"


@pytest.mark.asyncio
@pytest.mark.parametrize("parent_cancel", [False, True])
async def test_repair_extraction_suppressed_cancel_returns_with_recovery_owner(
    environment, parent_cancel
):
    host, plan, session, transport, _, _ = environment
    owner = HostOperations(ack_s=0.2, drain_s=0.02)
    session.extractor.limits = session.extractor.limits.model_copy(update={"timeout_s": 0.08})
    plan = plan.model_copy(update={"configuration_sha256": run.configuration_digest(session, plan)})
    host = replace(host, authorize=lambda supplied: plan, operations=owner)
    entered, release = asyncio.Event(), asyncio.Event()
    provider = session.extractor.provider
    runtime = session.extractor.runtime
    starts = []
    original_start = runtime.start

    async def tracked_start(box, request):
        starts.append(request)
        return await original_start(box, request)

    async def suppress(box, bundle):
        entered.set()
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass

    runtime.stage, runtime.start = suppress, tracked_start
    task = asyncio.create_task(run.execute_run(host, plan.request))
    try:
        async with asyncio.timeout(2):
            await entered.wait()
        if parent_cancel:
            task.cancel()
        done, _ = await asyncio.wait((task,), timeout=0.3)
        assert done, "Extraction must return even while its real _one suppresses cancellation"
        if parent_cancel:
            with pytest.raises(asyncio.CancelledError):
                task.result()
        else:
            assert task.result().status == "refused"
        assert owner.unsettled(plan.identity) and owner.recovery_required(plan.identity)
        assert provider.created and not provider.destroyed
        assert host.jobs.get(plan.identity).status == "creation_unknown"
        with session.runner.registry.transaction() as state:
            with pytest.raises(SandboxError):
                require_recovered(state.history(task_only=False))
        assert (await run.execute_run(host, plan.request)).category == "recovery_unavailable"
        assert not starts and transport.starts == 0
    finally:
        release.set()
        done, _ = await asyncio.wait((task,), timeout=2)
        assert done
        if not task.cancelled():
            task.exception()
        pending = owner.unsettled(plan.identity)
        if pending:
            done, remaining = await asyncio.wait(pending, timeout=2)
            assert not remaining
        await asyncio.sleep(0)
    assert len(provider.destroyed) == 1
    assert not starts and transport.starts == 0
    assert owner.recovery_required(plan.identity), "Late destruction is not a recovery receipt"


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_kind", ["lead", "extraction"])
@pytest.mark.parametrize(
    "operation,stage,fault",
    [
        ("stdout", "stdout", AssertionError),
        ("stdout_open", "stdout", TypeError),
        ("wait", "wait", TypeError),
        ("cancel", "cancel", AssertionError),
    ],
)
async def test_repair_native_process_faults_keep_safe_stage_diagnostics(
    environment, runtime_kind, operation, stage, fault
):
    host, plan, session, transport, _, _ = environment
    secret = "seller-secret-never-record-this"
    if runtime_kind == "lead":
        process = transport.process
    else:
        runtime = session.extractor.runtime
        start = runtime.start

    async def broken():
        raise fault(secret)

    async def broken_stream():
        raise fault(secret)
        yield b"unreachable"

    def inject(process):
        def broken_open():
            raise fault(secret)

        implementation = (
            broken_stream
            if operation == "stdout"
            else broken_open
            if operation == "stdout_open"
            else broken
        )
        setattr(process, stage, implementation)

    if runtime_kind == "lead":
        inject(process)
    else:

        async def faulty_start(box, request):
            process = await start(box, request)
            inject(process)
            return process

        runtime.start = faulty_start

    result = await run.execute_run(host, plan.request)
    assert result.category == "internal_error"
    diagnostic = result.diagnostic
    assert diagnostic.error_type == fault.__name__
    assert diagnostic.stage == f"{runtime_kind}.{stage}"
    assert 0 < len(diagnostic.frames) <= 8
    assert set(diagnostic.model_dump()) == {"error_type", "stage", "frames"}
    assert all(
        set(frame.model_dump()) == {"module", "function", "line"} for frame in diagnostic.frames
    )
    assert secret not in result.model_dump_json()
    assert host.operations.faults
    assert host.jobs.get(plan.identity).status not in {"completed", "stopped", "failed"}


@pytest.mark.asyncio
async def test_repair_successful_host_calls_remove_empty_identity_buckets(environment):
    host, plan, _, _, _, _ = environment
    owner = HostOperations()
    job = host.jobs.claim(plan.identity, owner_id=plan.owner_id, now=datetime.now(UTC)).job

    async def acknowledged():
        return "acknowledged"

    for index in range(200):
        distinct = job.model_copy(
            update={"identity": job.identity.model_copy(update={"task_id": f"task-{index}"})}
        )
        assert await owner.call(distinct, acknowledged()) == "acknowledged"
    assert not owner._tasks
    assert not owner._unknown


@pytest.mark.asyncio
async def test_repair_settled_unknown_host_call_keeps_separate_recovery_marker(environment):
    host, plan, _, _, _, _ = environment
    owner = HostOperations(ack_s=0.01, drain_s=0.01)
    job = host.jobs.claim(plan.identity, owner_id=plan.owner_id, now=datetime.now(UTC)).job
    release = asyncio.Event()

    async def suppress():
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass

    try:
        with pytest.raises(SandboxError):
            await owner.call(job, suppress())
        assert owner.unsettled(plan.identity)
    finally:
        pending = owner.unsettled(plan.identity)
        release.set()
        if pending:
            _, remaining = await asyncio.wait(pending, timeout=1)
            assert not remaining
        await asyncio.sleep(0)
    assert not owner._tasks
    assert owner.recovery_required(plan.identity)


@pytest.mark.asyncio
async def test_repair_host_bucket_settlement_preserves_other_live_operations(environment):
    host, plan, _, _, _, _ = environment
    owner = HostOperations(ack_s=0.2, drain_s=0.02)
    job = host.jobs.claim(plan.identity, owner_id=plan.owner_id, now=datetime.now(UTC)).job
    entered, release = asyncio.Event(), asyncio.Event()

    async def pending():
        entered.set()
        await release.wait()

    async def acknowledged():
        return True

    observer = asyncio.create_task(owner.call(job, pending()))
    try:
        await entered.wait()
        assert await owner.call(job, acknowledged()) is True
        assert len(owner.unsettled(plan.identity)) == 1
        assert owner.recovery_required(plan.identity)
    finally:
        release.set()
        await observer
    assert not owner._tasks and not owner.recovery_required(plan.identity)


def test_repair_run_is_explicit_builtin_and_does_not_change_plugins():
    assert list(discover_plugins()) == []
    assert "run" in get_command(create_app()).commands
    assert "run" not in get_command(create_app(plugins=[])).commands


def test_repair_cli_retains_real_extraction_batch_after_bounded_return(environment):
    host, plan, session, transport, _, _ = environment
    owner = HostOperations(ack_s=0.2, drain_s=0.02)
    session.extractor.limits = session.extractor.limits.model_copy(update={"timeout_s": 0.08})
    plan = plan.model_copy(update={"configuration_sha256": run.configuration_digest(session, plan)})
    host = replace(host, authorize=lambda supplied: plan, operations=owner)
    release = asyncio.Event()

    async def suppress(box, bundle):
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass

    session.extractor.runtime.stage = suppress
    install_run_host(host)
    started = time.monotonic()
    try:
        result = CliRunner().invoke(
            create_app(), ["run", "--deal", plan.request.deal, "--request", plan.request.request]
        )
        assert result.exit_code == 1
        assert time.monotonic() - started < 3
        assert json.loads(result.stdout)["category"] == "host_operation_unknown"
        assert owner.unsettled(plan.identity) and owner.recovery_required(plan.identity)
        assert len(owner.retained_loops) == 1
        assert session.extractor.provider.created and not session.extractor.provider.destroyed
        assert transport.starts == 0
    finally:
        install_run_host(None)
        release.set()
        for loop in owner.retained_loops:
            _, pending = loop.run_until_complete(asyncio.wait(asyncio.all_tasks(loop), timeout=2))
            assert not pending
            loop.run_until_complete(asyncio.sleep(0))
            assert not asyncio.all_tasks(loop)
            loop.close()
    assert len(session.extractor.provider.destroyed) == 1
    assert owner.recovery_required(plan.identity)


@pytest.mark.asyncio
async def test_repair_native_cancel_fault_records_diagnostic_without_losing_parent_cancel(
    environment,
):
    host, plan, _, transport, _, _ = environment
    transport.process.silent = True

    async def faulty_cancel():
        raise AssertionError("seller-secret-never-record-this")

    transport.process.cancel = faulty_cancel
    task = asyncio.create_task(run.execute_run(host, plan.request))
    async with asyncio.timeout(2):
        while not transport.starts:
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert host.operations.faults[-1].stage == "lead.cancel"
    assert host.operations.faults[-1].error_type == "AssertionError"
    assert "seller-secret-never-record-this" not in host.operations.faults[-1].model_dump_json()
    assert host.jobs.get(plan.identity).status == "start_unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["context", "registry", "configuration", "source"])
async def test_repair_watchdog_checkpoint_rechecks_pins_after_nudge(environment, drift):
    host, plan, session, _, evidence, _ = environment
    plan = plan.model_copy(update={"stuck": StuckLimits(repeat_limit=1, window_s=120)})
    registry = session.runner.registry
    other = plan.context.model_copy(
        update={"scope": TenantScope(user_id="other-user", firm_id="other-firm")}
    )
    job = host.jobs.claim(plan.identity, owner_id=plan.owner_id, now=datetime.now(UTC)).job
    normalizer = Normalizer(plan.segment, plan.workspace, session.runner.sanitizer)
    state = RunnerState(registry)
    release = asyncio.Event()
    prior_count = 0

    async def events(*args):
        yield state.append(normalizer.make("error", {"category": "synthetic_repeat"}))
        await release.wait()

    async def drifting(job):
        nonlocal prior_count
        with registry.transaction() as transaction:
            prior_count = sum(
                e.payload.get("binding") == "run_watchdog" for e in transaction.history()
            )
        if drift == "context":
            registry.context = other
        elif drift == "registry":
            session.runner.registry = copy(registry)
        elif drift == "configuration":
            role = registry.settings.models.roles["lead"]
            registry.settings.models.roles["lead"] = role.model_copy(update={"profile": "changed"})
        else:
            (session.preparser.raw_root / "rent_roll.csv").write_text("rent\n101\n200\n301\n")

    session.runner.run_segment = events
    evidence.nudge = drifting
    try:
        async with asyncio.timeout(1):
            with pytest.raises(Refusal) as refusal:
                await run._lead(session, plan, host, job)
        assert refusal.value.category == "binding_mismatch"
        with registry.engine.connect() as connection:
            assert not ToolState(connection, other).history()
            assert (
                sum(
                    e.payload.get("binding") == "run_watchdog"
                    for e in ToolState(connection, plan.context).history()
                )
                == prior_count
            )
    finally:
        registry.context = plan.context
        session.runner.registry = registry
        release.set()


@pytest.mark.asyncio
async def test_repair_refused_duplicate_does_not_cancel_active_owner(environment):
    host, plan, _, _, _, calls = environment
    job = host.jobs.claim(plan.identity, owner_id=plan.owner_id, now=datetime.now(UTC)).job
    entered, release, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def blocking():
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    task = asyncio.create_task(host.operations.call(job, blocking()))
    try:
        await entered.wait()
        result = await run.execute_run(host, plan.request)
        assert result.category == "recovery_unavailable"
        assert not calls
        assert not cancelled.is_set()
        assert not task.done()
        assert not host.operations.recovery_required(
            plan.identity, observed_task=host.operations.unsettled(plan.identity)[0]
        )
        assert host.jobs.get(plan.identity) == job
    finally:
        release.set()
        await task


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["stdout", "wait", "cancel"])
async def test_repair_native_await_drift_never_writes_another_tenant(environment, operation):
    host, plan, session, transport, _, _ = environment
    registry = session.runner.registry
    other = plan.context.model_copy(
        update={"scope": TenantScope(user_id="other-user", firm_id="other-firm")}
    )
    original = getattr(transport.process, operation)

    if operation == "stdout":

        async def drifting_stdout():
            async for line in original():
                registry.context = other
                yield line

        transport.process.stdout = drifting_stdout
    else:

        async def drifting():
            result = await original()
            registry.context = other
            return result

        setattr(transport.process, operation, drifting)

    try:
        result = await run.execute_run(host, plan.request)
        assert result.category == "binding_mismatch"
        assert transport.process.cancelled
        with registry.engine.connect() as connection:
            assert not ToolState(connection, other).history(task_only=False)
            history = ToolState(connection, plan.context).history()
            assert any(e.kind == "segment_end" for e in history)
            assert any(e.kind == "usage" and e.runner == "codex" for e in history)
    finally:
        registry.context = plan.context


@pytest.mark.asyncio
async def test_repair_unsettled_lead_stage_cannot_launch_after_parent_returns(environment):
    host, plan, session, transport, _, _ = environment
    host = replace(host, operations=HostOperations(ack_s=0.2, drain_s=0.02))
    plan = plan.model_copy(update={"cleanup_s": 10, "stuck": StuckLimits(window_s=120)})
    host = replace(host, authorize=lambda supplied: plan)
    entered, release = asyncio.Event(), asyncio.Event()

    async def suppress(box, bundle):
        entered.set()
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass

    transport.stage = suppress
    task = asyncio.create_task(run.execute_run(host, plan.request))
    try:
        async with asyncio.timeout(2):
            await entered.wait()
        task.cancel()
        done, _ = await asyncio.wait((task,), timeout=12)
        assert done, "A cancellation-resistant stage must not retain its caller"
        with pytest.raises(asyncio.CancelledError):
            await task
        retained = host.operations.unsettled(plan.identity)
        assert retained, "The lead producer must remain explicitly owned"
        assert host.operations.recovery_required(plan.identity)
        refused = await run.execute_run(host, plan.request)
        assert refused.category == "recovery_unavailable"
        release.set()
        settled, pending = await asyncio.wait(retained, timeout=2)
        assert not pending
        assert settled and transport.starts == 0
        assert host.operations.recovery_required(plan.identity)
    finally:
        release.set()
        await asyncio.wait(tuple(host.operations.unsettled(plan.identity)) or (task,), timeout=2)


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["configuration", "source"])
async def test_repair_nudge_rechecks_pins_before_delivery(environment, drift):
    host, plan, session, transport, evidence, _ = environment
    transport.process.silent = True
    wait = transport.process.stdout

    async def drifting():
        if drift == "configuration":
            registry = session.runner.registry
            role = registry.settings.models.roles["lead"]
            registry.settings.models.roles["lead"] = role.model_copy(update={"profile": "changed"})
        else:
            (session.preparser.raw_root / "rent_roll.csv").write_text("rent\n101\n200\n301\n")
        async for line in wait():
            yield line

    transport.process.stdout = drifting
    result = await run.execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert not evidence.nudges
    assert transport.process.cancelled


@pytest.mark.asyncio
async def test_repair_native_cleanup_retains_original_ledger_engine(environment):
    host, plan, session, transport, _, _ = environment
    registry, original = session.runner.registry, transport.process.wait
    engine = registry.engine
    changed = create_engine("sqlite://")
    metadata.create_all(changed)

    async def drifting_wait():
        result = await original()
        registry.engine = changed
        return result

    transport.process.wait = drifting_wait
    try:
        result = await run.execute_run(host, plan.request)
        assert result.category == "binding_mismatch"
        assert transport.process.cancelled
        with changed.connect() as connection:
            assert not ToolState(connection, plan.context).history(task_only=False)
        with engine.connect() as connection:
            history = ToolState(connection, plan.context).history()
            assert any(
                e.kind == "segment_end" and e.payload.get("usage_complete") is True for e in history
            )
    finally:
        registry.engine = engine
        changed.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["stdout", "wait", "cancel"])
@pytest.mark.parametrize("drift", ["context", "engine"])
async def test_repair_extraction_cleanup_retains_original_ledger(environment, operation, drift):
    host, plan, session, transport, _, _ = environment
    registry, start = session.runner.registry, session.extractor.runtime.start
    engine, context = registry.engine, registry.context
    other = context.model_copy(
        update={"scope": TenantScope(user_id="other-user", firm_id="other-firm")}
    )
    changed = create_engine("sqlite://")
    metadata.create_all(changed)
    processes = []

    def mutate():
        if drift == "context":
            registry.context = other
        else:
            registry.engine = changed

    async def drifting_start(box, request):
        process = await start(box, request)
        processes.append(process)
        original = getattr(process, operation)
        if operation == "stdout":

            async def stdout():
                async for line in original():
                    mutate()
                    yield line

            process.stdout = stdout
        else:

            async def awaited():
                result = await original()
                mutate()
                return result

            setattr(process, operation, awaited)
        return process

    session.extractor.runtime.start = drifting_start
    try:
        result = await run.execute_run(host, plan.request)
        assert result.category == "binding_mismatch"
        assert processes and processes[0].cancelled
        assert transport.starts == 0
        with changed.connect() as connection:
            assert not ToolState(connection, context).history(task_only=False)
        with engine.connect() as connection:
            assert not ToolState(connection, other).history(task_only=False)
            history = ToolState(connection, context).history()
            assert any(e.kind == "usage" and e.payload.get("extraction_attempt") for e in history)
            assert any(
                e.payload.get("binding") == "extraction_attempt" and e.payload.get("phase") == "end"
                for e in history
            )
    finally:
        registry.context, registry.engine = context, engine
        changed.dispose()
