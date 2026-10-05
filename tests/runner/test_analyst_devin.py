"""Offline HTTP contracts only; no live sessions or containment evidence."""

import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from pydantic import SecretStr

from cre_brain.analyst.devin import DevinDraftClient, DevinDraftConfig, DevinDraftError


class Journal:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(deepcopy(event))

    def existing(self, turn_id):
        return any(e["turn_id"] == turn_id for e in self.events)

    def pending(self):
        latest = {e["turn_id"]: e["phase"] for e in self.events}
        return any(phase != "closed" for phase in latest.values())


def config(**changes):
    return DevinDraftConfig(
        api_key=SecretStr("unit-test-placeholder-not-a-real-key"),
        org_id="org-test",
        outpost_pool="test-outpost-pool",
        security_profile_id="profile-test",
        poll_seconds=0.001,
        **changes,
    )


class API:
    def __init__(self, **changes):
        self.requests = []
        self.payload = None
        self.value = {
            "session_id": "devin-test",
            "org_id": "org-test",
            "status": "running",
            "status_detail": "finished",
            "devin_mode": "normal",
            "security_profile": {"selection": "profile", "profile_id": "profile-test"},
            "child_session_ids": [],
            "structured_output": {"turn_id": "turn-a"},
            "acus_consumed": 0.2,
            **changes,
        }
        self.create_status = 200

    def __call__(self, request):
        self.requests.append(request)
        assert request.url.host == "api.devin.ai"
        if request.method == "POST":
            self.payload = json.loads(request.content)
            return httpx.Response(
                self.create_status,
                json={
                    "session_id": "devin-test",
                    "org_id": "org-test",
                    "status": "new",
                    "acus_consumed": 0,
                },
            )
        if request.method == "DELETE":
            self.value["status"] = "exit"
        return httpx.Response(200, json=self.value)


async def decide(client):
    return await client.decide(
        role="lead",
        instructions="Test-only trusted charter",
        context={"synthetic": True},
        schema={"type": "object"},
        turn_id="turn-a",
    )


@pytest.mark.asyncio
async def test_devin_draft_posts_narrow_request_and_records_unverified_closed_receipt():
    api, journal = API(), Journal()
    client = DevinDraftClient(config=config(), journal=journal, transport=httpx.MockTransport(api))
    assert await decide(client) == {"turn_id": "turn-a"}
    payload = api.payload
    assert payload["repos"] == payload["knowledge_ids"] == payload["secret_ids"] == []
    assert payload["resumable"] is False
    assert payload["bypass_approval"] is False
    assert payload["platform"] == "test-outpost-pool"
    assert payload["max_acu_limit"] == 2
    assert payload["structured_output_required"] is True
    assert "unit-test-placeholder-not-a-real-key" not in json.dumps(payload)
    receipt = journal.events[-1]
    assert receipt["phase"] == "closed"
    assert receipt["token_caps_verified"] is False
    assert receipt["descendant_containment_verified"] is False
    assert receipt["evidence"] == "unverified_public_development"
    assert [r.method for r in api.requests] == ["POST", "GET", "GET", "DELETE"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"devin_mode": "fast"},
        {"security_profile": None},
        {"structured_output": {"turn_id": "stale"}},
        {"acus_consumed": 3},
        {"status": "suspended", "status_detail": "usage_limit_exceeded"},
        {"status_detail": "waiting_for_approval"},
    ],
)
async def test_devin_draft_rejects_unbound_blocked_or_stale_output_and_closes(changes):
    api, journal = API(**changes), Journal()
    client = DevinDraftClient(config=config(), journal=journal, transport=httpx.MockTransport(api))
    with pytest.raises(DevinDraftError):
        await decide(client)
    assert api.requests[-1].method == "DELETE"
    assert journal.events[-1]["phase"] == "closed"
    calls = len(api.requests)
    with pytest.raises(DevinDraftError, match="reconciliation"):
        await decide(client)
    assert len(api.requests) == calls


@pytest.mark.asyncio
async def test_uncertain_create_is_not_retried_or_falsely_reported_as_terminated():
    api, journal = API(), Journal()
    api.create_status = 503
    client = DevinDraftClient(config=config(), journal=journal, transport=httpx.MockTransport(api))
    with pytest.raises(DevinDraftError, match="HTTP 503"):
        await decide(client)
    assert journal.pending()
    with pytest.raises(DevinDraftError, match="reconciliation"):
        await decide(client)
    assert len(api.requests) == 1
    assert journal.events[-1]["phase"] == "intent"


@pytest.mark.asyncio
async def test_unexpected_descendants_do_not_produce_a_false_cleanup_receipt():
    api, journal = API(child_session_ids=["devin-unexpected"]), Journal()
    client = DevinDraftClient(config=config(), journal=journal, transport=httpx.MockTransport(api))
    with pytest.raises(DevinDraftError, match="Termination is unconfirmed"):
        await decide(client)
    assert journal.pending()
    assert journal.events[-1]["phase"] == "created"


@pytest.mark.asyncio
async def test_probe_cancellation_closes_known_session_but_does_not_claim_runtime_caps():
    api, journal = API(status_detail="working", structured_output=None), Journal()
    client = DevinDraftClient(config=config(), journal=journal, transport=httpx.MockTransport(api))
    task = asyncio.create_task(decide(client))
    for _ in range(100):
        if len(api.requests) >= 2:
            break
        await asyncio.sleep(0.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert journal.events[-1]["phase"] == "closed"
    assert journal.events[-1]["descendant_containment_verified"] is False


@pytest.mark.parametrize("pool", ["linux", "windows", "macos", "inherit", "default", " test "])
def test_draft_requires_explicit_outpost_not_silent_cloud_placement(pool):
    with pytest.raises(ValueError):
        DevinDraftConfig.model_validate({**config().model_dump(), "outpost_pool": pool})


def test_api_secret_repr_is_masked_and_production_purpose_is_rejected():
    assert "unit-test-placeholder-not-a-real-key" not in repr(config())
    with pytest.raises(ValueError):
        DevinDraftConfig.model_validate({**config().model_dump(), "purpose": "customer_production"})
