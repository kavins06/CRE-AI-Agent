"""Scaffold interface checks; do not substitute for tenant/runtime/gate integration."""

from pathlib import Path

import pytest
from pydantic import ValidationError


def test_t001_ac4_tenant_scope_is_typed_immutable_and_fail_closed() -> None:
    from cre_brain.domain.base import TenantScope

    scope = TenantScope(user_id=" user-a ", firm_id="firm-a")
    assert scope.user_id == "user-a"
    with pytest.raises(ValidationError):
        TenantScope(user_id="", firm_id="firm-a")
    with pytest.raises(ValidationError):
        TenantScope(user_id="user-a", firm_id=" ")
    with pytest.raises(ValidationError):
        TenantScope(user_id="user-a", firm_id="firm-a", token="not-permitted")
    with pytest.raises(ValidationError):
        scope.firm_id = "firm-b"


def test_t001_ac4_runner_is_streaming_not_awaitable_contract(tmp_path: Path) -> None:
    import subprocess
    import sys

    source = tmp_path / "contract.py"
    source.write_text(
        "from collections.abc import AsyncIterator\n"
        "from pydantic import BaseModel\n"
        "from cre_brain.runner.base import Runner, Policy\n"
        "class Payload(BaseModel):\n"
        "    value: str\n"
        "class Deny:\n"
        "    def check(self, action: Payload) -> bool:\n"
        "        return False\n"
        "class Stream:\n"
        "    async def run_segment(self, seg: Payload, ws: Payload, policy: Deny)"
        " -> AsyncIterator[Payload]:\n"
        "        yield seg\n"
        "policy: Policy[Payload, bool] = Deny()\n"
        "runner: Runner[Payload, Payload, Deny, Payload] = Stream()\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(source)],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    source.write_text(
        source.read_text().replace(
            "runner: Runner[Payload, Payload, Deny, Payload] = Stream()",
            "runner: Runner[Payload, Payload, Deny, Payload] = Deny()",
        )
    )
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(source)],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "incompatible" in result.stdout.lower()


def test_t001_ac4_state_and_deliverable_seams_require_explicit_scope() -> None:
    import inspect

    from cre_brain.deliverables.base import DeliverableFinalizer
    from cre_brain.state.base import VersionedStore

    for fn in (VersionedStore.append, VersionedStore.get, DeliverableFinalizer.finalize):
        scope = inspect.signature(fn).parameters["scope"]
        assert scope.default is inspect.Parameter.empty
        assert scope.kind is inspect.Parameter.KEYWORD_ONLY
    for protocol in (VersionedStore, DeliverableFinalizer):
        with pytest.raises(TypeError):
            protocol()
