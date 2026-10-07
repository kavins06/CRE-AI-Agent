"""Run the existing T037 gates in the same canonical transaction as new Facts."""

from datetime import UTC, datetime

from cre_brain.gates.service import GateService
from cre_brain.gates.state import CanonicalState
from cre_brain.runner.tools.state import ToolState


def transactional(service: GateService, state: ToolState) -> GateService:
    if state.scope != service.scope or state.connection.engine is not service.engine:
        raise ValueError("Gate transaction must belong to the authenticated canonical store")
    view = GateService(
        service.engine,
        scope=service.scope,
        settings=service.settings,
        inputs=service.inputs,
        scratch=service.scratch,
    )
    view.state = CanonicalState(
        service.engine,
        service.scope,
        service.inputs,
        datetime.now(UTC).date(),
        connection=state.connection,
    )
    return view
