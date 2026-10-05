"""Host artifact bindings over the existing T032 provider; canonical records stay in SQL."""

from cre_brain.deliverables.screen.models import Document
from cre_brain.rules.models import Policy
from cre_brain.runner.tools.contracts import (
    Artifact,
    AuthenticatedContext,
    FactAnchor,
    InputProvider,
    Template,
)


class ScreenInputs:
    def __init__(self, source: InputProvider) -> None:
        self.source = source
        self._artifacts: dict[tuple[str, ...], Artifact] = {}
        self._documents: dict[tuple[str, ...], Document] = {}

    @staticmethod
    def key(context: AuthenticatedContext, identity: str) -> tuple[str, ...]:
        return (
            context.scope.user_id,
            context.scope.firm_id,
            context.task_id,
            context.deal_id,
            context.release_id,
            identity,
        )

    def register_document(self, context: AuthenticatedContext, document: Document) -> None:
        """Host intake pins canonical document identity to its descriptor before SCREEN.

        This method is not exposed as an analyst tool. Authentication/extraction
        of the raw source remains the host's responsibility.
        """
        document = Document.model_validate(document.model_dump())
        key = self.key(context, document.doc_id)
        if key in self._documents and self._documents[key] != document:
            raise ValueError("Authenticated document descriptors are immutable")
        self._documents[key] = document

    def document(self, context: AuthenticatedContext, identity: str) -> Document | None:
        document = self._documents.get(self.key(context, identity))
        return Document.model_validate(document.model_dump()) if document is not None else None

    def register(self, context: AuthenticatedContext, artifact: Artifact) -> None:
        artifact = Artifact.model_validate(artifact.model_dump())
        key = self.key(context, artifact.deliverable.d_id)
        if key in self._artifacts and self._artifacts[key] != artifact:
            raise ValueError("SCREEN artifact bindings are immutable")
        self._artifacts[key] = artifact

    def artifact(self, context: AuthenticatedContext, identity: str) -> Artifact | None:
        artifact = self._artifacts.get(self.key(context, identity))
        if artifact is None:
            return self.source.artifact(context, identity)
        return Artifact.model_validate(artifact.model_dump())

    def fact(self, context: AuthenticatedContext, identity: str) -> FactAnchor | None:
        return self.source.fact(context, identity)

    def template(self, context: AuthenticatedContext, identity: str) -> Template | None:
        return self.source.template(context, identity)

    def rule_policy(self, context: AuthenticatedContext, table: str) -> Policy | None:
        return self.source.rule_policy(context, table)
