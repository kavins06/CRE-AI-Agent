"""Compare actual pytest collections of committed revisions in isolated archives."""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest


class Counter:
    def __init__(self) -> None:
        self.count = 0

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.count = len(session.items)


def collect(root: Path) -> int:
    counter = Counter()
    status = pytest.main(
        [
            "tests",
            "--collect-only",
            "-p",
            "pytest_asyncio.plugin",
            "-p",
            "pytest_cov.plugin",
            "-p",
            "_hypothesis_pytestplugin",
            "-q",
            "-o",
            "addopts=",
            "--basetemp",
            str(root / ".cache" / "count"),
        ],
        plugins=[counter],
    )
    if status != 0 or not counter.count:
        raise ValueError(f"Collection failed or empty (exit {status})")
    return counter.count


def count_revision(
    repo: Path, revision: str, target: Path, *, prescaffold_base: bool = False
) -> int:
    archive = subprocess.check_output(["git", "archive", revision], cwd=repo)
    target.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(target, filter="data")
    if not (target / "tests").exists():
        if prescaffold_base:
            return 0
        raise ValueError(f"{revision} contains no tests directory")
    (target / ".cache").mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment.pop("PYTEST_PLUGINS", None)
    environment.update(
        PYTEST_ADDOPTS="", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONPATH=str(target / "src")
    )
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--collect", str(target)],
        cwd=target,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise ValueError(f"{revision} collection failed:\n{result.stdout}\n{result.stderr}")
    return int(result.stdout.rsplit("COLLECTED=", 1)[1].strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--base", default="origin/dev")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--collect", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.collect:
            print(f"COLLECTED={collect(args.collect)}")
            return 0
        with tempfile.TemporaryDirectory(prefix="cre-count-") as temp:
            base = count_revision(args.root, args.base, Path(temp) / "base", prescaffold_base=True)
            head = count_revision(args.root, args.head, Path(temp) / "head")
        print(f"Collected tests: base={base} head={head}")
        if head < base:
            print("Dropped test count", file=sys.stderr)
            return 1
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Test-count check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
