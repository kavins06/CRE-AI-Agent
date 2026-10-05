"""Rules first over host document metadata; uncertainty never invokes a model here."""

import re
from pathlib import PurePath

from cre_brain.deliverables.screen.models import Classification, Document


class RuleDecisionModel:
    def classify(self, document: Document) -> Classification:
        document = Document.model_validate(document.model_dump())
        suffix = PurePath(document.filename).suffix.lower()
        if suffix not in {".pdf", ".xlsx", ".csv"}:
            return Classification(doc_id=document.doc_id, kind="unsupported")
        title = PurePath(document.filename).stem.lower().replace("_", " ").replace("-", " ")
        matches = [
            kind
            for kind, pattern in (
                ("om", r"\b(?:om|offering memorandum|offering memo)\b"),
                ("rent_roll", r"\brent roll\b"),
                ("t12", r"\b(?:t12|t 12|trailing twelve)\b"),
                ("lease", r"\blease\b"),
            )
            if re.search(pattern, title)
        ]
        if len(matches) != 1:
            return Classification(
                doc_id=document.doc_id, kind="ambiguous" if matches else "unknown"
            )
        return Classification.model_validate({"doc_id": document.doc_id, "kind": matches[0]})
