"""Provider-neutral Excel recalculation seam."""

from pathlib import Path
from typing import Protocol


class ExcelEngine(Protocol):
    def recalc(self, path: Path) -> Path: ...
