from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture
def public_probe_path() -> Iterator[Path]:
    with TemporaryDirectory(prefix="cre-public-probe-") as directory:
        yield Path(directory)
