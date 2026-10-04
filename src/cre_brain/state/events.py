"""Durable, sequenced event ingestion with task-scoped reconnect idempotency."""

from pydantic import TypeAdapter
from sqlalchemy import Engine, and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from cre_brain.domain import AgentEvent
from cre_brain.domain.base import Identifier, TenantScope
from cre_brain.domain.models import NonnegativeInt
from cre_brain.state.schema import events
from cre_brain.state.store import StateConflict, lock_append, tenant_filter

identifier = TypeAdapter(Identifier)
nonnegative = TypeAdapter(NonnegativeInt)


class EventStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def append(self, event: AgentEvent, *, scope: TenantScope) -> AgentEvent:
        event = AgentEvent.model_validate(event.model_dump())
        task_filter = and_(tenant_filter(events, scope), events.c.task_id == event.task_id)
        identity = events.c.event_id == event.event_id
        if event.origin is not None:
            box, segment, local_seq = event.origin
            identity = or_(
                identity,
                and_(
                    events.c.task_id == event.task_id,
                    events.c.origin_box == box,
                    events.c.origin_segment == segment,
                    events.c.origin_local_seq == local_seq,
                ),
            )
        try:
            with self.engine.begin() as connection:
                lock_append(connection, scope, ("events", event.task_id))
                existing = (
                    connection.execute(
                        select(events.c.payload).where(tenant_filter(events, scope), identity)
                    )
                    .scalars()
                    .all()
                )
                if existing:
                    if len(existing) != 1:
                        raise StateConflict("Event ID and origin refer to different events")
                    stored = AgentEvent.model_validate(existing[0])
                    excluded = {"seq", "event_id"}
                    if stored.model_dump(mode="json", exclude=excluded) != event.model_dump(
                        mode="json", exclude=excluded
                    ):
                        raise StateConflict("Event replay conflicts with its immutable origin")
                    return stored
                last = connection.execute(select(func.max(events.c.seq)).where(task_filter))
                assigned = event.model_copy(update={"seq": int(last.scalar_one() or 0) + 1})
                origin = assigned.origin or (None, None, None)
                connection.execute(
                    events.insert().values(
                        user_id=scope.user_id,
                        firm_id=scope.firm_id,
                        event_id=assigned.event_id,
                        task_id=assigned.task_id,
                        seq=assigned.seq,
                        origin_box=origin[0],
                        origin_segment=origin[1],
                        origin_local_seq=origin[2],
                        payload=assigned.model_dump(mode="json"),
                    )
                )
                return assigned
        except IntegrityError:
            raise StateConflict("Event identity conflicts with existing history") from None

    def list(
        self, task_id: str, *, scope: TenantScope, after_seq: int = 0, limit: int = 100
    ) -> list[AgentEvent]:
        task_id = identifier.validate_python(task_id)
        after_seq = nonnegative.validate_python(after_seq)
        limit = nonnegative.validate_python(limit)
        if not 1 <= limit <= 1000:
            raise ValueError("Event page limit must be between 1 and 1000")
        query = (
            select(events.c.payload)
            .where(
                tenant_filter(events, scope),
                events.c.task_id == task_id,
                events.c.seq > after_seq,
            )
            .order_by(events.c.seq)
            .limit(limit)
        )
        with self.engine.connect() as connection:
            payloads = connection.execute(query).scalars()
            return [AgentEvent.model_validate(payload) for payload in payloads]
