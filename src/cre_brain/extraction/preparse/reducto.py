"""Licensed seam only. No Reducto HTTP client or successful-empty fallback.

Optional live adapter tests must use ``pytest.mark.requires_license("REDUCTO")``.
The license attestation and installed transport come from trusted configuration,
not seller documents. Unit seam tests do not prove licensed service parsing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import ConfigDict

from cre_brain.extraction.preparse.models import Boundary, Limits, ParserUnavailable, PdfContent


@runtime_checkable
class ReductoTransport(Protocol):
    def convert(self, content: bytes, *, filename: str, limits: Limits) -> PdfContent:
        """Return bounded typed PDF text with page dimensions/top-left point boxes."""
        ...


class ReductoAdapter(Boundary):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    licensed: bool = False
    transport: ReductoTransport | None = None

    def require_available(self) -> None:
        if not self.licensed:
            raise ParserUnavailable("REDUCTO license is unavailable")
        if self.transport is None:
            raise ParserUnavailable("REDUCTO licensed transport is not configured")

    def convert(self, content: bytes, *, filename: str, limits: Limits) -> PdfContent:
        self.require_available()
        assert self.transport is not None
        result = self.transport.convert(content, filename=filename, limits=limits)
        return PdfContent.model_validate_json(result.model_dump_json())
