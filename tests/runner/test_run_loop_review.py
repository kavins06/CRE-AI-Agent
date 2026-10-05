"""Public synthetic review regressions; no T040 acceptance or native runtime evidence."""

import asyncio
import json
import re
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_run_loop import environment as run_environment

from cre_brain.deliverables.screen import ScreenInputs
from cre_brain.domain import Deliverable
from cre_brain.gates.models import MemoPair
from cre_brain.runner.normalizer import Normalizer
from cre_brain.runner.orchestration import run
from cre_brain.runner.orchestration.stuck import StuckLimits
from cre_brain.runner.tools.contracts import Artifact, ArtifactCompanion
from cre_brain.runner.tools.json_io import canonical
from cre_brain.state import publications

environment = run_environment


@pytest.mark.asyncio
async def test_review_profile_drift_during_capabilities_precedes_extraction(environment):
    host, plan, session, transport, _, _ = environment
    capabilities = transport.capabilities
    extract = session.extractor.extract
    invoked = []

    async def drifting(box):
        role = transport.registry.settings.models.roles["lead"]
        transport.registry.settings.models.roles["lead"] = role.model_copy(
            update={"profile": "changed"}
        )
        return await capabilities(box)

    async def tracked(identities):
        invoked.append(identities)
        return await extract(identities)

    transport.capabilities = drifting
    session.extractor.extract = tracked
    result = await run.execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert not invoked and transport.starts == 0


@pytest.mark.asyncio
async def test_review_source_drift_after_extraction_precedes_native_start(environment):
    host, plan, session, transport, _, _ = environment
    extract = session.extractor.extract

    async def drifting(identities):
        result = await extract(identities)
        (session.preparser.raw_root / "rent_roll.csv").write_text("rent\n101\n200\n301\n")
        return result

    session.extractor.extract = drifting
    result = await run.execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert transport.starts == 0


@pytest.mark.asyncio
async def test_review_second_capability_drift_cannot_publish_or_launch(environment):
    host, plan, session, transport, _, _ = environment
    capabilities = transport.capabilities
    start = transport.start
    count = 0
    attempts = []
    prepared = []

    async def drifting(box):
        nonlocal count
        count += 1
        if count == 2:
            from cre_brain.gates import GateService

            previous = transport.registry.gates
            transport.registry.gates = GateService(
                previous.engine,
                scope=previous.scope,
                inputs=previous.inputs,
                settings=previous.settings,
                scratch=previous.scratch,
            )
            prepared.append(
                session.screen.run(
                    documents=tuple(p.descriptor for p in plan.sources),
                    headlines=dict(plan.headlines),
                    run_id="review-prepared",
                )
            )
        return await capabilities(box)

    async def publishing(box, request):
        for prepared_run in prepared:
            attempts.extend(
                transport.registry.call("finalize_deliverable", {"deliverable_id": identity})
                for identity in prepared_run.deliverable_ids
            )
        return await start(box, request)

    transport.capabilities = drifting
    transport.start = publishing
    result = await run.execute_run(host, plan.request)
    assert result.category == "binding_mismatch"
    assert transport.starts == 0
    assert not any(a["status"] == "ok" for a in attempts)
    with transport.registry.transaction() as state:
        assert not any(d.status == "final" for d in state.all_current(Deliverable))


@pytest.mark.asyncio
async def test_review_independent_authority_blocks_gate_replacement_during_start(environment):
    host, plan, session, transport, _, _ = environment
    start = transport.start
    attempts = []

    async def publishing(box, request):
        from cre_brain.gates import GateService

        gate = transport.registry.gates
        transport.registry.gates = GateService(
            gate.engine,
            scope=gate.scope,
            inputs=gate.inputs,
            settings=gate.settings,
            scratch=gate.scratch,
        )
        draft = session.screen.run(
            documents=tuple(p.descriptor for p in plan.sources),
            headlines=dict(plan.headlines),
            run_id="review-during-start",
        )
        attempts.extend(
            transport.registry.call("finalize_deliverable", {"deliverable_id": identity})
            for identity in draft.deliverable_ids
        )
        return await start(box, request)

    transport.start = publishing
    await run.execute_run(host, plan.request)
    assert attempts and all(a["status"] == "refused" for a in attempts)
    with transport.registry.transaction() as state:
        assert not any(d.status == "final" for d in state.all_current(Deliverable))


@pytest.mark.asyncio
async def test_review_lifecycle_authority_blocks_existing_final_and_idempotent_replay(environment):
    host, plan, session, transport, _, _ = environment
    registry = transport.registry
    for pin in plan.sources:
        registry.inputs.register_document(plan.context, pin.descriptor)
    earlier = session.screen.run(
        documents=tuple(p.descriptor for p in plan.sources),
        headlines=dict(plan.headlines),
        run_id="review-earlier",
    )
    for identity in earlier.deliverable_ids:
        assert registry.call("finalize_deliverable", {"deliverable_id": identity})["status"] == "ok"
    job = host.jobs.claim(plan.identity, owner_id=plan.owner_id, now=datetime.now(UTC)).job
    registry.bind_publication_authority(
        run.RunPublicationAuthority(
            host,
            run.NativeClaim(
                identity=job.identity, owner_id=job.owner_id, claim_revision=job.claim_revision
            ),
            plan.context,
        )
    )
    attempts = [
        registry.call("finalize_deliverable", {"deliverable_id": earlier.deliverable_ids[0]}),
        registry.call(
            "finalize_deliverable",
            {"deliverable_id": earlier.deliverable_ids[1]},
            request_id="new-final-replay",
        ),
    ]
    assert job.status == "creation_unknown"
    assert len(attempts) == 2 and all(a["status"] == "refused" for a in attempts)


def replace_publications(session, result):
    """Authorized synthetic replacement rows with actual canonical gates/publication."""
    registry = session.runner.registry
    authority = session.screen.authority
    bodies = {}
    old = {}
    with registry.transaction() as state:
        for identity in result.deliverable_ids:
            current = state.current(Deliverable, identity)
            anchor, _ = publications.load_release(
                state.connection, registry.context, identity, current.version
            )
            old[identity] = current, anchor
            path = Path(anchor.deliverable.path)
            if path.suffix == ".md":
                bodies[str(path)] = path.read_bytes() + b"\nHost revision.\n"
    for _, anchor in old.values():
        path = Path(anchor.deliverable.path)
        if path.suffix == ".json":
            md = next(c for c in anchor.companions if c.path.suffix == ".md")
            bodies[str(path)] = canonical({"markdown": bodies[str(md.path)].decode()}).encode()
    for path, body in bodies.items():
        Path(path).write_bytes(body)
    replacement = ScreenInputs(registry.inputs.source)
    for document in registry.inputs._documents.values():
        replacement.register_document(registry.context, document)
    registry.inputs = session.screen.inputs = replacement
    for identity, (current, anchor) in old.items():
        draft = current.model_copy(
            update={
                "status": "draft",
                "version": current.version + 1,
                "parent_version": current.version,
                "gate_results": [],
            }
        )
        with registry.transaction() as state:
            state.append(draft)
        original = authority.plan(registry.context.scope, anchor.deliverable)
        memo = original.memo_pair
        updated = original.model_copy(
            update={
                "memo_pair": MemoPair(
                    markdown=memo.markdown,
                    json_path=memo.json_path,
                    markdown_sha256=run.hashlib.sha256(bodies[str(memo.markdown)]).hexdigest(),
                    json_sha256=run.hashlib.sha256(bodies[str(memo.json_path)]).hexdigest(),
                )
            }
        )
        authority.put_plan(registry.context.scope, draft, updated)
        replacement.register(
            registry.context,
            Artifact(
                deliverable=draft,
                sha256=run.hashlib.sha256(bodies[draft.path]).hexdigest(),
                companions=tuple(
                    ArtifactCompanion(
                        path=c.path, sha256=run.hashlib.sha256(bodies[str(c.path)]).hexdigest()
                    )
                    for c in anchor.companions
                ),
            ),
        )
        response = registry.call(
            "finalize_deliverable", {"deliverable_id": identity}, request_id="revision-" + identity
        )
        assert response["status"] == "ok", response
        assert response["data"]["version"] == 4


@pytest.mark.asyncio
async def test_review_manifest_never_replays_newer_authorized_publications(environment):
    host, plan, session, transport, _, _ = environment
    first = await run.execute_run(host, plan.request)
    assert first.status == "ok"
    replace_publications(session, first)
    replay = await run.execute_run(host, plan.request)
    assert replay.status == "refused"
    assert transport.starts == 1


@pytest.mark.asyncio
async def test_review_manifest_pins_original_versions_references_and_hashes(environment):
    host, plan, session, _, _, _ = environment
    first = await run.execute_run(host, plan.request)
    assert first.status == "ok"
    with session.runner.registry.transaction() as state:
        manifest = next(
            e.payload for e in state.history() if e.payload.get("binding") == "run_publications"
        )
        pins = manifest["result"]["publications"]
        assert len(pins) == 2
        for pin in pins:
            assert pin["version"] == 2
            _, stored = publications.load_release(
                state.connection, plan.context, pin["deliverable_id"], pin["version"]
            )
            assert [(p["publication_id"], p["sha256"], p["size"]) for p in pin["entries"]] == [
                (p.publication_id, p.sha256, len(p.body)) for p in stored
            ]
            assert all(run.hashlib.sha256(p.body).hexdigest() == p.sha256 for p in stored)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["nudge", "receipt"])
async def test_review_unknown_host_operation_retains_owned_task(environment, operation):
    from cre_brain.runner.orchestration.run_operations import HostOperations

    host, plan, session, transport, evidence, _ = environment
    owner = HostOperations(ack_s=0.02, drain_s=0.02)
    host = replace(host, operations=owner)
    release, entered = asyncio.Event(), asyncio.Event()

    async def suppress(*args):
        entered.set()
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass
        if operation == "receipt":
            raise ValueError("Synthetic unknown receipt")

    if operation == "nudge":
        transport.process.silent = True
        evidence.nudge = suppress
    else:
        evidence.verify = suppress
    try:
        async with asyncio.timeout(3):
            result = await run.execute_run(host, plan.request)
        assert entered.is_set() and result.status == "refused"
        assert owner.unsettled(plan.identity)
        assert owner.recovery_required(plan.identity)
        assert host.jobs.get(plan.identity).status not in {"completed", "stopped", "failed"}
        assert (await run.execute_run(host, plan.request)).category == "recovery_unavailable"
    finally:
        release.set()
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_review_post_nudge_repeated_errors_remain_observable(environment):
    host, plan, session, _, evidence, _ = environment
    plan = plan.model_copy(update={"stuck": StuckLimits(repeat_limit=1, window_s=120)})
    job = host.jobs.claim(plan.identity, owner_id=plan.owner_id, now=datetime.now(UTC)).job
    normalizer = Normalizer(plan.segment, plan.workspace, session.runner.sanitizer)
    state = run.RunnerState(session.runner.registry)

    async def events(*args):
        for _ in range(4):
            yield state.append(normalizer.make("error", {"category": "synthetic_repeat"}))
            await asyncio.sleep(0.02)

    session.runner.run_segment = events
    reason = await run._lead(session, plan, host, job)
    assert reason == "repeated_error"
    assert len(evidence.nudges) == 1
    with session.runner.registry.transaction() as transaction:
        checkpoint = [
            e.payload["checkpoint"]
            for e in transaction.history()
            if e.payload.get("binding") == "run_watchdog"
        ][-1]
    assert checkpoint["stopped"] is True and checkpoint["last_seq"] >= 2


@pytest.mark.asyncio
async def test_review_wall_clock_jumps_cannot_accelerate_watchdog(environment):
    host, plan, _, transport, evidence, _ = environment
    baseline = datetime.now(UTC)
    counter = 0

    def jumped():
        nonlocal counter
        counter += 1
        return baseline + timedelta(seconds=counter * 121)

    plan = plan.model_copy(update={"stuck": StuckLimits(window_s=120)})
    host = replace(host, authorize=lambda supplied: plan, clock=jumped)
    transport.process.silent = True
    task = asyncio.create_task(run.execute_run(host, plan.request))
    started = time.monotonic()
    try:
        async with asyncio.timeout(3):
            while transport.starts == 0:
                await asyncio.sleep(0.01)
        await asyncio.sleep(0.1)
        assert not evidence.nudges, "Wall time must not advance a monotonic deadline"
        assert time.monotonic() - started < 1
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_review_partial_tests_do_not_match_acceptance_namespace():
    names = re.findall(
        r"(?:async )?def (test_\w+)", Path(__file__).with_name("test_run_loop.py").read_text()
    )
    assert not [name for name in names if re.match(r"test_t040_ac\d+_", name)]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [AssertionError, KeyError, TypeError, ValueError])
async def test_review_programmer_fault_is_diagnosable_without_raw_messages(environment, fault):
    host, plan, _, _, _, _ = environment

    def broken(request):
        raise fault("seller-secret-never-record-this")

    result = await run.execute_run(replace(host, authorize=broken), plan.request)
    assert result.category == "internal_error"
    assert result.diagnostic.error_type == fault.__name__
    assert result.diagnostic.frames
    assert "seller-secret-never-record-this" not in result.model_dump_json()


def test_review_cli_does_not_use_unbounded_asyncio_run_shutdown(environment, monkeypatch):
    from typer.testing import CliRunner

    from cre_brain.cli import create_app
    from cre_brain.runner.run_commands import install_run_host

    host, plan, _, _, _, _ = environment

    def forbidden(operation):
        operation.close()
        raise AssertionError("Do not delegate shutdown to unbounded asyncio.run")

    monkeypatch.setattr(asyncio, "run", forbidden)
    install_run_host(host)
    try:
        result = CliRunner().invoke(
            create_app(), ["run", "--deal", plan.request.deal, "--request", plan.request.request]
        )
    finally:
        install_run_host(None)
    assert result.exit_code == 0, result.exception
    assert json.loads(result.stdout)["status"] == "ok"


def test_review_cli_retains_cancellation_suppressing_receipt(environment):
    from typer.testing import CliRunner

    from cre_brain.cli import create_app
    from cre_brain.runner.orchestration.run_operations import HostOperations
    from cre_brain.runner.run_commands import install_run_host

    host, plan, _, _, evidence, _ = environment
    owner = HostOperations(ack_s=0.02, drain_s=0.02)
    host = replace(host, operations=owner)
    release = asyncio.Event()

    async def suppress(job):
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass
        raise ValueError("Synthetic unknown receipt")

    evidence.verify = suppress
    install_run_host(host)
    started = time.monotonic()
    try:
        result = CliRunner().invoke(
            create_app(), ["run", "--deal", plan.request.deal, "--request", plan.request.request]
        )
        assert result.exit_code == 1
        assert time.monotonic() - started < 3
        assert owner.unsettled(plan.identity) and owner.recovery_required(plan.identity)
        assert len(owner.retained_loops) == 1
        assert host.jobs.get(plan.identity).status == "start_unknown"
    finally:
        install_run_host(None)
        release.set()
        for loop in owner.retained_loops:
            loop.run_until_complete(asyncio.sleep(0.05))
            assert not asyncio.all_tasks(loop)
            loop.close()


@pytest.mark.asyncio
async def test_review_receipt_value_error_keeps_safe_diagnostic(environment):
    host, plan, _, _, evidence, _ = environment

    async def broken(job):
        raise ValueError("seller-secret-never-record-this")

    evidence.verify = broken
    result = await run.execute_run(host, plan.request)
    assert result.category == "receipt_unavailable"
    assert result.diagnostic.error_type == "ValueError"
    assert "seller-secret-never-record-this" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_review_stage_await_drift_precedes_native_start(environment):
    host, plan, _, transport, _, _ = environment

    async def drifting(box, bundle):
        role = transport.registry.settings.models.roles["lead"]
        transport.registry.settings.models.roles["lead"] = role.model_copy(
            update={"profile": "changed"}
        )

    transport.stage = drifting
    result = await run.execute_run(host, plan.request)
    assert result.status == "refused"
    assert transport.starts == 0


@pytest.mark.asyncio
async def test_review_extraction_capability_await_drift_precedes_model_start(environment):
    host, plan, session, transport, _, _ = environment
    runtime = session.extractor.runtime
    capabilities = runtime.capabilities
    start = runtime.start
    invoked = []

    async def drifting(box, bundle):
        role = transport.registry.settings.models.roles["lead"]
        transport.registry.settings.models.roles["lead"] = role.model_copy(
            update={"profile": "changed"}
        )
        return await capabilities(box, bundle)

    async def tracked(box, request):
        invoked.append(request)
        return await start(box, request)

    runtime.capabilities = drifting
    runtime.start = tracked
    result = await run.execute_run(host, plan.request)
    assert result.status == "refused"
    assert not invoked and transport.starts == 0


@pytest.mark.asyncio
async def test_review_stage_programmer_fault_retains_safe_diagnostic(environment):
    host, plan, _, transport, _, _ = environment

    async def broken(box, bundle):
        raise AssertionError("seller-secret-never-record-this")

    transport.stage = broken
    result = await run.execute_run(host, plan.request)
    assert result.category == "internal_error"
    assert result.diagnostic.error_type == "AssertionError"
    assert "seller-secret-never-record-this" not in result.model_dump_json()
    assert transport.starts == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["nudge", "receipt"])
async def test_review_parent_cancellation_drains_and_retains_host_work(environment, operation):
    from cre_brain.runner.orchestration.run_operations import HostOperations

    host, plan, _, transport, evidence, _ = environment
    owner = HostOperations(ack_s=0.2, drain_s=0.02)
    host = replace(host, operations=owner)
    entered, release = asyncio.Event(), asyncio.Event()

    async def suppress(*args):
        entered.set()
        while not release.is_set():
            try:
                await release.wait()
            except asyncio.CancelledError:
                pass

    if operation == "nudge":
        transport.process.silent = True
        evidence.nudge = suppress
    else:
        evidence.verify = suppress
    task = asyncio.create_task(run.execute_run(host, plan.request))
    try:
        async with asyncio.timeout(3):
            await entered.wait()
            started = time.monotonic()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert time.monotonic() - started < 1
        assert owner.unsettled(plan.identity) and owner.recovery_required(plan.identity)
        assert host.jobs.get(plan.identity).status == "start_unknown"
    finally:
        release.set()
        await asyncio.sleep(0.05)
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
