"""Re-run the exact verify for every passing feature (CI main/nightly only)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def verify(root: Path) -> int:
    features = json.loads((root / "feature_list.json").read_text())["features"]
    failures = []
    for feature in features:
        if not feature["passes"]:
            continue
        print(f"Verifying {feature['id']}: {feature['verify']}", flush=True)
        result = subprocess.run(feature["verify"], shell=True, cwd=root, timeout=1800)
        if result.returncode:
            failures.append(feature["id"])
    if failures:
        print("Failed verifies: " + ", ".join(failures), file=sys.stderr)
    return int(bool(failures))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        return verify(args.root)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"Feature verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
