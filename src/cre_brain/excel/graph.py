"""Licensed Microsoft Graph Excel seam; no client or credential access yet."""

from pathlib import Path


class GraphExcelEngine:
    implemented = False

    def recalc(self, path: Path) -> Path:
        raise NotImplementedError(
            "GraphExcelEngine is a licensed stub; configure the future Graph provider"
        )
