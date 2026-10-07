"""Persistent host ownership of bounded acknowledgements and safe fault diagnostics.

Cancellation is cooperative in Python. Unsettled operations remain owned here;
no timeout or late settlement proves native absence or authorizes a retry.
"""

import asyncio
import re
import time
from collections import deque
from collections.abc import Coroutine
from typing import Any

from pydantic import Field

from cre_brain.control.jobs import Job, JobIdentity
from cre_brain.runner.tools.contracts import ID, Boundary
from cre_brain.sandbox.base import SandboxError


class HostOperationUnknown(SandboxError):
    pass


class FaultFrame(Boundary):
    module: ID
    function: ID
    line: int = Field(strict=True, ge=0)


class FaultDiagnostic(Boundary):
    error_type: ID
    stage: ID = "host"
    frames: tuple[FaultFrame, ...] = Field(max_length=8)


def _identifier(value: object) -> str:
    value = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(value))[:128]
    return value or "unknown"


class HostOperations:
    def __init__(self, *, ack_s: float = 5, drain_s: float = 1) -> None:
        if not 0 < ack_s <= 5 or not 0 < drain_s <= 30:
            raise ValueError("Host operation bounds must be positive and finite")
        self.ack_s, self.drain_s = ack_s, drain_s
        self._tasks: dict[str, set[asyncio.Task[Any]]] = {}
        self._unknown: set[str] = set()
        self.retained_loops: list[asyncio.AbstractEventLoop] = []
        self.faults: list[FaultDiagnostic] = []

    @staticmethod
    def key(identity: JobIdentity) -> str:
        return identity.model_dump_json()

    def unsettled(self, identity: JobIdentity) -> tuple[asyncio.Task[Any], ...]:
        return tuple(t for t in self._tasks.get(self.key(identity), ()) if not t.done())

    def recovery_required(
        self, identity: JobIdentity, *, observed_task: asyncio.Task[Any] | None = None
    ) -> bool:
        # A guard inside the exact currently observed extraction batch may exclude
        # that healthy task. Unknown outcomes always require recovery, even there.
        return self.key(identity) in self._unknown or any(
            task is not observed_task for task in self.unsettled(identity)
        )

    def mark_unknown(self, identity: JobIdentity) -> None:
        self._unknown.add(self.key(identity))

    def own[T](self, identity: JobIdentity, task: asyncio.Task[T]) -> asyncio.Task[T]:
        key = self.key(identity)
        tasks = self._tasks.setdefault(key, set())
        tasks.add(task)

        def settled(done: asyncio.Task[T]) -> None:
            tasks.discard(done)
            if not tasks:
                self._tasks.pop(key, None)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(settled)
        return task

    def record_fault(self, error: Exception, *, stage: str = "host") -> FaultDiagnostic:
        frames: deque[FaultFrame] = deque(maxlen=8)
        trace = error.__traceback__
        while trace is not None:
            frames.append(
                FaultFrame(
                    module=_identifier(trace.tb_frame.f_globals.get("__name__", "host")),
                    function=_identifier(trace.tb_frame.f_code.co_name),
                    line=trace.tb_lineno,
                )
            )
            trace = trace.tb_next
        diagnostic = FaultDiagnostic(
            error_type=_identifier(type(error).__name__),
            stage=_identifier(stage),
            frames=tuple(frames),
        )
        self.faults.append(diagnostic)
        self.faults[:] = self.faults[-128:]
        return diagnostic  # Never exception messages, locals, filenames or raw traceback strings.

    async def _drain(
        self, tasks: tuple[asyncio.Task[Any], ...], interruptions: list[asyncio.CancelledError]
    ) -> None:
        deadline = time.monotonic() + self.drain_s
        pending = {task for task in tasks if not task.done()}
        while pending and time.monotonic() < deadline:
            try:
                _, pending = await asyncio.wait(
                    pending, timeout=max(0, deadline - time.monotonic())
                )
            except asyncio.CancelledError as error:
                interruptions.append(error)

    async def call[T](
        self, job: Job, operation: Coroutine[Any, Any, T], *, timeout_s: float | None = None
    ) -> T:
        observation_s = self.ack_s if timeout_s is None else timeout_s
        if not 0 < observation_s <= 86400:
            operation.close()
            raise ValueError("Host observation bound must be positive and finite")
        key = self.key(job.identity)
        task = self.own(job.identity, asyncio.create_task(operation))
        interruptions: list[asyncio.CancelledError] = []
        try:
            done, _ = await asyncio.wait((task,), timeout=observation_s)
            if not done:
                self._unknown.add(key)
                raise HostOperationUnknown("Host acknowledgement outcome requires recovery")
            return task.result()
        except BaseException as error:
            if isinstance(error, asyncio.CancelledError):
                interruptions.append(error)
            if not task.done():
                self._unknown.add(key)
                task.cancel()
                await self._drain((task,), interruptions)
            if interruptions:
                raise interruptions[0] from None
            raise

    async def cancel_owned(self, identity: JobIdentity) -> None:
        tasks = self.unsettled(identity)
        interruptions: list[asyncio.CancelledError] = []
        if tasks:
            self._unknown.add(self.key(identity))
        for task in tasks:
            task.cancel()
        await self._drain(tasks, interruptions)
        if interruptions:
            raise interruptions[0]

    def retain_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Embedding must supervise/terminate its worker; these coroutines cannot be killed.

        Keeping the loop avoids asyncio.run's unbounded shutdown wait. It does
        not make suppressed work safe, nor automatically resume the retained loop.
        """
        self.retained_loops.append(loop)
