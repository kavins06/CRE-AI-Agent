"""Behavioral tests for task/collection guards using real isolated pytest processes."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=90)


def suite(tmp_path: Path, source: str, *, policy: bool = True) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_example.py").write_text(source)
    if policy:
        shutil.copy(ROOT / "tests/conftest.py", tmp_path / "tests/conftest.py")
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    return tmp_path


def pytest_run(root: Path, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return run(sys.executable, "-m", "pytest", "tests", "-q", cwd=root, env=env)


@pytest.mark.parametrize(
    "violation",
    [
        '@pytest.mark.skip(reason="evade")\ndef test_example(): pass',
        '@pytest.mark.skipif(True, reason="evade")\ndef test_example(): pass',
        "@pytest.mark.xfail\ndef test_example(): pass",
        'def test_example(): pytest.skip("evade")',
        'def test_example(): pytest.xfail("evade")',
        'pytest.skip("evade", allow_module_level=True)',
    ],
)
def test_t002_ac1_rejects_unapproved_marked_and_dynamic_skips(
    tmp_path: Path, violation: str
) -> None:
    result = pytest_run(suite(tmp_path, "import pytest\n" + violation + "\n"))
    assert result.returncode != 0, result.stdout + result.stderr
    assert "Unapproved" in result.stdout + result.stderr


def test_t002_ac1_only_prerequisite_markers_can_skip(tmp_path: Path) -> None:
    root = suite(
        tmp_path,
        """
import pytest
@pytest.mark.requires_key("MISSING_TEST_KEY")
def test_key(): raise AssertionError("must not run")
@pytest.mark.requires_license("MISSING_TEST_LICENSE")
def test_license(): raise AssertionError("must not run")
@pytest.mark.requires_network
def test_network(): raise AssertionError("must not run")
""",
    )
    env = os.environ.copy()
    for name in ("MISSING_TEST_KEY", "MISSING_TEST_LICENSE", "CRE_NETWORK_ENABLED"):
        env.pop(name, None)
    result = pytest_run(root, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "3 skipped" in result.stdout


def test_t002_ac1_present_key_does_not_authorize_manual_skip(tmp_path: Path) -> None:
    root = suite(
        tmp_path,
        """
import pytest
@pytest.mark.requires_key("PRESENT_TEST_KEY")
def test_key(): pytest.skip("evade")
""",
    )
    result = pytest_run(root, {**os.environ, "PRESENT_TEST_KEY": "synthetic"})
    assert result.returncode != 0
    assert "Unapproved" in result.stdout


def task_fixture(root: Path, source: str, *, policy: bool = False) -> Path:
    suite(root, source, policy=policy)
    (root / "task.md").write_text(
        "- [ ] AC1 (`test_t900_ac1_*`): one\n- [ ] AC2 (`test_t900_ac2_*`): two\n"
    )
    (root / "feature_list.json").write_text(
        json.dumps(
            {
                "features": [
                    {
                        "id": "T900",
                        "task_file": "task.md",
                        "passes": False,
                        "verify": "unused",
                    }
                ]
            }
        )
    )
    return root


def checker(root: Path) -> subprocess.CompletedProcess[str]:
    return run(
        sys.executable, str(ROOT / "scripts/check_task.py"), "T900", "--root", str(root), cwd=root
    )


def test_t002_ac2_runs_tests_and_requires_each_ac(tmp_path: Path) -> None:
    root = task_fixture(tmp_path, "def test_t900_ac1_ok(): pass\n")
    result = checker(root)
    assert result.returncode != 0
    assert "AC2" in result.stdout + result.stderr
    (root / "tests/test_example.py").write_text(
        "def test_t900_ac1_ok(): pass\ndef test_t900_ac2_ok(): pass\n"
    )
    result = checker(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "AC1" in result.stdout and "AC2" in result.stdout


def test_t002_ac2_skips_and_failures_are_not_passes(tmp_path: Path) -> None:
    root = task_fixture(
        tmp_path,
        """
import pytest
def test_t900_ac1_ok(): pass
@pytest.mark.requires_key("MISSING_TEST_KEY")
def test_t900_ac2_unavailable(): pass
""",
        policy=True,
    )
    result = checker(root)
    assert result.returncode != 0
    assert "AC2" in result.stdout + result.stderr
    (root / "tests/test_example.py").write_text(
        "def test_t900_ac1_ok(): pass\ndef test_t900_ac2_bad(): assert False\n"
    )
    assert checker(root).returncode != 0


def test_t002_ac2_all_skipped_and_empty_ac_list_fail(tmp_path: Path) -> None:
    root = task_fixture(
        tmp_path,
        """
import pytest
pytestmark = pytest.mark.requires_key("MISSING_TEST_KEY")
def test_t900_ac1_ok(): pass
def test_t900_ac2_ok(): pass
""",
        policy=True,
    )
    result = checker(root)
    assert result.returncode != 0
    assert "all" in (result.stdout + result.stderr).lower()
    (root / "task.md").write_text("No numbered criteria\n")
    assert checker(root).returncode != 0


def git(root: Path, *args: str) -> str:
    result = run("git", *args, cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def commit_fixture(root: Path) -> str:
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    return git(root, "rev-parse", "HEAD")


def test_t002_ac3_compares_real_collected_git_revisions(tmp_path: Path) -> None:
    root = suite(tmp_path, "def test_one(): pass\ndef test_two(): pass\n", policy=False)
    git(root, "init", "--initial-branch=dev")
    base = commit_fixture(root)
    (root / "tests/test_example.py").write_text("def test_one(): pass\n")
    commit_fixture(root)
    result = run(
        sys.executable,
        str(ROOT / "scripts/test_count.py"),
        "--root",
        str(root),
        "--base",
        base,
        cwd=root,
    )
    assert result.returncode != 0
    assert "base=2" in result.stdout and "head=1" in result.stdout
    (root / "tests/test_example.py").write_text("def test_one(): pass\ndef test_two(): pass\n")
    commit_fixture(root)
    result = run(
        sys.executable,
        str(ROOT / "scripts/test_count.py"),
        "--root",
        str(root),
        "--base",
        base,
        cwd=root,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_t002_ac4_reexecutes_passing_verifies_only_and_propagates_failure(tmp_path: Path) -> None:
    (tmp_path / "feature_list.json").write_text(
        json.dumps(
            {
                "features": [
                    {"id": "T900", "passes": True, "verify": "printf reran > evidence; exit 7"},
                    {"id": "T901", "passes": False, "verify": "touch forbidden"},
                ]
            }
        )
    )
    result = run(
        sys.executable,
        str(ROOT / "scripts/verify_features.py"),
        "--root",
        str(tmp_path),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert (tmp_path / "evidence").read_text() == "reran"
    assert not (tmp_path / "forbidden").exists()
    make = run("make", "--dry-run", "check", cwd=ROOT)
    assert "verify_features" not in make.stdout


def test_t002_ac5_ci_job_triggers_and_docker_cache() -> None:
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]["pull_request"]["branches"]) == {"dev", "main"}
    assert workflow["on"]["schedule"]
    jobs = workflow["jobs"]
    assert {"check", "test-count", "verify-features"} <= jobs.keys()
    assert any(step.get("run") == "make check" for step in jobs["check"]["steps"])
    guard = jobs["verify-features"]["if"]
    assert "schedule" in guard and "main" in guard and "pull_request" in guard
    all_steps = [step for job in jobs.values() for step in job["steps"]]
    assert any(step.get("uses", "").startswith("actions/cache@") for step in all_steps)
    assert any("docker save" in step.get("run", "") for step in all_steps)
    assert any("docker load" in step.get("run", "") for step in all_steps)
    assert any("test_count.py" in step.get("run", "") for step in all_steps)


def test_t002_ac6_missing_tests_not_spoofed_by_existing_report(tmp_path: Path) -> None:
    root = task_fixture(tmp_path, "def test_t900_ac1_ok(): pass\n")
    (root / "stale.xml").write_text(
        '<testsuite><testcase name="test_t900_ac2_spoofed"/></testsuite>'
    )
    result = checker(root)
    assert result.returncode != 0
    assert "AC2" in result.stdout + result.stderr


def test_t002_ac6_scripts_fail_closed_on_collection_errors(tmp_path: Path) -> None:
    root = task_fixture(tmp_path, "not valid Python!\n")
    assert checker(root).returncode != 0
