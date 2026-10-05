"""Advisory record plumbing, never a live run or an acceptance transcript."""

import json
from pathlib import Path

import httpx
import pytest
from tests.runner.test_analyst_devin import API, config
from tests.runner.test_analyst_loop import ACCEPT, PLAN, StubClient, candidate
from typer.testing import CliRunner

from cre_brain.analyst.brain import load_brain
from cre_brain.analyst.devin import DevinDraftClient, RegistryProbeJournal
from cre_brain.analyst.loop import AnalystLoop
from cre_brain.analyst.record import AdvisoryRecordingSession, record_advisory
from cre_brain.cli import create_app
from cre_brain.runner.record_commands import install_advisory_record_factory
from cre_brain.runner.tools.json_io import canonical

pytest_plugins = ("tests.runner.test_tools_t032",)
ROOT = Path(__file__).resolve().parents[2]


class SequencedAPI(API):
    def __init__(self):
        super().__init__()
        self.responses = [PLAN, candidate(), ACCEPT]

    def __call__(self, request):
        if request.method == "POST":
            payload = json.loads(request.content)
            identity = f"devin-unit-{len(self.responses)}"
            self.value = {
                **self.value,
                "session_id": identity,
                "status": "running",
                "structured_output": {
                    "turn_id": payload["tags"][1],
                    **self.responses.pop(0),
                },
            }
            self.requests.append(request)
            return httpx.Response(
                200,
                json={
                    "session_id": identity,
                    "org_id": "org-test",
                    "status": "new",
                    "acus_consumed": 0,
                },
            )
        return super().__call__(request)


def test_advisory_record_defaults_to_missing_authenticated_host(tmp_path):
    install_advisory_record_factory(None)
    output = tmp_path / "not-created"
    result = CliRunner().invoke(
        create_app(),
        [
            "record",
            "--advisory-probe",
            "--request",
            "Synthetic request",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["category"] == "missing_runtime"
    assert not output.exists()


@pytest.mark.asyncio
async def test_advisory_record_refuses_stub_model_as_provider_evidence(tools, tmp_path):
    controller = AnalystLoop(
        brain=load_brain(ROOT / "brain"),
        client=StubClient([]),
        registry=tools[0],
    )
    with pytest.raises(ValueError, match="Host must authorize"):
        await record_advisory(
            AdvisoryRecordingSession(
                controller=controller,
                request="Synthetic",
                evidence={},
                run_id="probe",
            ),
            tmp_path / "stub",
            request="Synthetic",
        )


@pytest.mark.asyncio
async def test_advisory_record_is_hashed_host_bound_and_explicitly_unverified(
    tools, public_probe_path
):
    registry = tools[0]
    api = SequencedAPI()
    client = DevinDraftClient(
        config=config(),
        journal=RegistryProbeJournal(registry),
        transport=httpx.MockTransport(api),
    )
    controller = AnalystLoop(brain=load_brain(ROOT / "brain"), client=client, registry=registry)
    session = AdvisoryRecordingSession(
        controller=controller,
        request="Synthetic",
        evidence={},
        run_id="public-probe",
    )
    for output in (ROOT / "probe", public_probe_path / "transcripts" / "probe"):
        with pytest.raises(ValueError):
            await record_advisory(session, output, request="Synthetic")
    assert not api.requests
    output = public_probe_path / "public-probe"
    manifest = await record_advisory(session, output, request="Synthetic")
    assert manifest["evidence"] == "unverified_public_development"
    assert manifest["publication"] == "not_authorized"
    assert manifest["status"] == "reviewed_draft"
    assert json.loads((output / "result.json").read_text())["decision"]["recommendation"] == "hold"
    assert json.loads((output / "manifest.json").read_text()) == manifest
    with registry.transaction() as state:
        assert any(
            event.payload.get("advisory_probe_manifest_hash") == manifest["manifest_sha256"]
            for event in state.history()
        )
    before = canonical(manifest)
    with pytest.raises(ValueError, match="existing evidence"):
        await record_advisory(session, output, request="Synthetic")
    assert canonical(json.loads((output / "manifest.json").read_text())) == before
