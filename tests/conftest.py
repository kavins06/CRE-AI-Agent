"""Fail-closed skip policy: prerequisites are the only permitted skip source."""

from __future__ import annotations

import os
import re
import shutil
import subprocess

import pytest

APPROVED = {"requires_codex", "requires_network", "requires_key", "requires_license"}
AUTHORIZED = pytest.StashKey[bool]()


def pytest_configure(config: pytest.Config) -> None:
    for marker in APPROVED:
        config.addinivalue_line("markers", f"{marker}: explicit external prerequisite")
    if config.option.basetemp:
        from pathlib import Path

        Path(config.option.basetemp).parent.mkdir(parents=True, exist_ok=True)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        for mark in item.iter_markers():
            if mark.name in {"skip", "skipif", "xfail"}:
                raise pytest.UsageError(f"Unapproved skip/xfail marker on {item.nodeid}")
            if mark.name not in APPROVED:
                continue
            named = mark.name in {"requires_key", "requires_license"}
            if mark.kwargs or len(mark.args) != int(named):
                raise pytest.UsageError(f"Invalid prerequisite marker on {item.nodeid}")
            if named and (
                not isinstance(mark.args[0], str)
                or not re.fullmatch(r"[A-Z][A-Z0-9_]*", mark.args[0])
            ):
                raise pytest.UsageError(f"Invalid prerequisite name on {item.nodeid}")


def codex_available() -> bool:
    if not shutil.which("codex"):
        return False
    try:
        return (
            subprocess.run(
                ["codex", "login", "status"], capture_output=True, timeout=5, check=False
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


def pytest_runtest_setup(item: pytest.Item) -> None:
    item.stash[AUTHORIZED] = False
    for mark in item.iter_markers():
        reason = None
        if mark.name == "requires_codex" and not codex_available():
            reason = "SKIPPED_NO_RUNNER"
        elif mark.name == "requires_network" and os.environ.get("CRE_NETWORK_ENABLED") != "1":
            reason = "SKIPPED_NO_NETWORK"
        elif mark.name in {"requires_key", "requires_license"} and not os.environ.get(mark.args[0]):
            reason = "SKIPPED_NO_KEY" if mark.name == "requires_key" else "SKIPPED_NO_LICENSE"
        if reason:
            item.stash[AUTHORIZED] = True
            pytest.skip(reason)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    report = yield
    if hasattr(report, "wasxfail") or (
        report.skipped and not (report.when == "setup" and item.stash.get(AUTHORIZED, False))
    ):
        report.outcome = "failed"
        report.longrepr = f"Unapproved runtime skip/xfail: {item.nodeid}"
        if hasattr(report, "wasxfail"):
            del report.wasxfail
    return report


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if report.skipped:
        raise pytest.UsageError(f"Unapproved collection skip: {report.nodeid}")
