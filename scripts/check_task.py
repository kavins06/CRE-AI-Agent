"""Execute fresh acceptance tests; never trust an old report or a task's passes bit."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def check(task_id: str, root: Path) -> int:
    if not re.fullmatch(r"T[0-9]{3}", task_id):
        raise ValueError("Task ID must be T followed by three digits")
    features = json.loads((root / "feature_list.json").read_text())["features"]
    task = next((item for item in features if item["id"] == task_id), None)
    if task is None:
        raise ValueError(f"Unknown task: {task_id}")
    task_file = (root / task["task_file"]).resolve()
    if not task_file.is_relative_to(root.resolve()):
        raise ValueError("Task file must be inside the repository")
    acs = re.findall(r"^- \[.\] AC([0-9]+)\b", task_file.read_text(), flags=re.M)
    if not acs or len(set(acs)) != len(acs):
        raise ValueError("Task must define unique numbered ACs")
    with tempfile.TemporaryDirectory(prefix="cre-task-") as temp:
        report = Path(temp) / "results.xml"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests",
                "-k",
                f"test_{task_id.lower()}_",
                "--junitxml",
                str(report),
                "--basetemp",
                str(Path(temp) / "pytest"),
                "-q",
            ],
            cwd=root,
            env={**os.environ, "PYTEST_ADDOPTS": ""},
            capture_output=True,
            text=True,
            timeout=600,
        )
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        if not report.exists():
            raise ValueError("Pytest produced no acceptance report")
        cases = list(ET.parse(report).iter("testcase"))
        passed = [
            case.get("name", "")
            for case in cases
            if not any(case.find(status) is not None for status in ("skipped", "failure", "error"))
        ]
        missing = []
        for ac in acs:
            pattern = re.compile(rf"^test_{task_id.lower()}_ac{ac}_")
            if not any(pattern.match(name) for name in passed):
                missing.append(f"AC{ac}")
        if not passed:
            print("Task area has no passed tests (all skipped, failed or absent).", file=sys.stderr)
        if missing:
            print("Missing PASSED non-skipped tests: " + ", ".join(missing), file=sys.stderr)
        if result.returncode != 0 or missing or not passed:
            return 1
        print(f"{task_id}: " + ", ".join(f"AC{ac} PASSED" for ac in acs))
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        return check(args.task_id.upper(), args.root.resolve())
    except (ValueError, OSError, KeyError, ET.ParseError, subprocess.TimeoutExpired) as exc:
        print(f"Task check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
