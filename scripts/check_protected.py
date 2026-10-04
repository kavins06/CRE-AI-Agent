#!/usr/bin/env python3
"""Fail if a PR touches protected paths without the owner's `protected-change` label.

Owner-authored guard. Reads the protected list from the BASE ref (not the PR) so a PR
cannot weaken its own protection.

Usage (CI): check_protected.py --base origin/main [--labels "a,b"]
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys

LABEL = "protected-change"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def protected_patterns(base: str) -> list[str]:
    try:
        text = git("show", f"{base}:scripts/protected_paths.txt")
    except subprocess.CalledProcessError:
        # Bootstrap only: the base branch predates the guard list (the owner's first commit of it).
        print("protected-paths: base has no list yet; using this PR's list (bootstrap)")
        with open("scripts/protected_paths.txt", encoding="utf-8") as fh:
            text = fh.read()
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def changed_files(base: str) -> list[str]:
    out = git("diff", "--name-only", f"{base}...HEAD")
    return [ln for ln in out.splitlines() if ln]


def matches(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        # "dir/*" protects everything below dir/
        if pat.endswith("/*") and path.startswith(pat[:-1]):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--labels", default="")
    args = ap.parse_args()
    labels = {s.strip() for s in args.labels.split(",") if s.strip()}
    patterns = protected_patterns(args.base)
    hits = [f for f in changed_files(args.base) if matches(f, patterns)]
    if not hits:
        print("protected-paths: OK (no protected paths changed)")
        return 0
    print("protected-paths: this PR changes protected paths:")
    for h in hits:
        print(f"  - {h}")
    if LABEL in labels:
        print(f"protected-paths: OK (owner label '{LABEL}' present; CODEOWNERS review still required)")
        return 0
    print(f"protected-paths: FAIL. Owner must review and add label '{LABEL}'.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
