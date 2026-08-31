import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager


class ConcurrencyLimitError(Exception):
    """Raised when a concurrency slot cannot be acquired in time."""


class ConcurrencyController:
    def __init__(
        self,
        global_limit: int = 4,
        runner_limits: Mapping[str, int] | None = None,
        queue_wait_seconds: float = 5.0,
    ) -> None:
        if global_limit <= 0:
            raise ValueError("global_limit must be positive")
        if queue_wait_seconds < 0:
            raise ValueError("queue wait must be nonnegative")
        configured_limits = dict(runner_limits or {})
        if any(limit <= 0 for limit in configured_limits.values()):
            raise ValueError("runner limits must be positive")
        self._global = asyncio.Semaphore(global_limit)
        self._runner = {name: asyncio.Semaphore(limit) for name, limit in configured_limits.items()}
        self._queue_wait_seconds = queue_wait_seconds

    @asynccontextmanager
    async def slot(self, runner_name: str) -> AsyncIterator[None]:
        deadline = asyncio.get_running_loop().time() + self._queue_wait_seconds
        acquired_global = False
        acquired_runner = False
        runner_semaphore = self._runner.get(runner_name)
        try:
            try:
                await self._acquire(self._global, deadline)
                acquired_global = True
                if runner_semaphore is not None:
                    await self._acquire(runner_semaphore, deadline)
                    acquired_runner = True
            except TimeoutError as exc:
                raise ConcurrencyLimitError("concurrency capacity is unavailable") from exc
            yield
        finally:
            if acquired_runner and runner_semaphore is not None:
                runner_semaphore.release()
            if acquired_global:
                self._global.release()

    async def _acquire(self, semaphore: asyncio.Semaphore, deadline: float) -> None:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            if self._queue_wait_seconds == 0:
                if semaphore._value > 0:  # noqa: SLF001
                    await semaphore.acquire()
                    return
            raise TimeoutError
        await asyncio.wait_for(semaphore.acquire(), timeout=remaining)
