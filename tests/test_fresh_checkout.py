"""Bootstrap must work from Git source, never from ignored local artifacts."""

import io
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tracked_scaffold_bootstraps_in_a_fresh_archive(tmp_path: Path) -> None:
    tracked = subprocess.check_output(
        ["git", "ls-files", "src/cre_brain/memory/__init__.py"], cwd=ROOT, text=True
    )
    assert tracked.strip() == "src/cre_brain/memory/__init__.py"
    tree = subprocess.check_output(["git", "write-tree"], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(["git", "archive", tree], cwd=ROOT)
    checkout = tmp_path / "tracked checkout"
    checkout.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(checkout, filter="data")
    subprocess.run(
        ["git", "init", "--initial-branch=dev", str(checkout)], check=True, capture_output=True
    )
    assert not (checkout / ".cache").exists()
    result = subprocess.run(
        [str(checkout / "init.sh")], cwd=tmp_path, text=True, capture_output=True, timeout=120
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (checkout / ".cache").is_dir()
    result = subprocess.run(
        [str(checkout / ".venv/bin/python"), "-m", "pytest", "tests/test_t001_scaffold.py", "-q"],
        cwd=checkout,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
