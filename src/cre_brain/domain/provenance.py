"""Usable source locations shared by composition and independent release gates."""

from cre_brain.domain.models import Provenance


def usable_anchor(provenance: Provenance) -> bool:
    return bool(
        provenance.doc_id.strip()
        and (
            provenance.page is not None
            or (
                provenance.sheet is not None
                and provenance.sheet.strip()
                and provenance.cell is not None
                and provenance.cell.strip()
            )
        )
    )
