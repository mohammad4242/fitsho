import asyncio
from collections.abc import Coroutine
from typing import Any

import pytest

from app.concurrency import ConcurrencyController, ConcurrencyLimitError


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def test_controller_bounds_global_and_runner_concurrency() -> None:
    async def scenario() -> tuple[int, int]:
        controller = ConcurrencyController(global_limit=2, runner_limits={"codex": 1})
        active_global = 0
        active_runner = 0
        max_global = 0
        max_runner = 0

        async def work() -> None:
            nonlocal active_global, active_runner, max_global, max_runner
            async with controller.slot("codex"):
                active_global += 1
                active_runner += 1
                max_global = max(max_global, active_global)
                max_runner = max(max_runner, active_runner)
                await asyncio.sleep(0.03)
                active_runner -= 1
                active_global -= 1

        await asyncio.gather(*(work() for _ in range(4)))
        return max_global, max_runner

    assert run(scenario()) == (1, 1)


def test_controller_allows_different_runners_up_to_global_limit() -> None:
    async def scenario() -> int:
        controller = ConcurrencyController(global_limit=2, runner_limits={"codex": 2, "claude": 2})
        active = 0
        maximum = 0

        async def work(name: str) -> None:
            nonlocal active, maximum
            async with controller.slot(name):
                active += 1
                maximum = max(maximum, active)
                await asyncio.sleep(0.03)
                active -= 1

        await asyncio.gather(work("codex"), work("claude"), work("codex"))
        return maximum

    assert run(scenario()) == 2


def test_queue_overflow_raises_and_slot_is_released() -> None:
    async def scenario() -> None:
        controller = ConcurrencyController(global_limit=1, queue_wait_seconds=0.02)

        async def holder() -> None:
            async with controller.slot("codex"):
                await asyncio.sleep(0.1)

        first = asyncio.create_task(holder())
        await asyncio.sleep(0)
        with pytest.raises(ConcurrencyLimitError, match="capacity"):
            async with controller.slot("codex"):
                pass
        await first

        async with controller.slot("codex"):
            pass

    run(scenario())


def test_zero_queue_window_never_waits_for_an_occupied_slot() -> None:
    async def scenario() -> None:
        controller = ConcurrencyController(global_limit=1, queue_wait_seconds=0)
        async with controller.slot("codex"):
            with pytest.raises(ConcurrencyLimitError):
                async with controller.slot("codex"):
                    pass

    run(scenario())


def test_cancelled_waiter_does_not_consume_slot() -> None:
    async def scenario() -> None:
        controller = ConcurrencyController(global_limit=1, queue_wait_seconds=1)

        async with controller.slot("codex"):
            waiter = asyncio.create_task(_hold_slot(controller))
            await asyncio.sleep(0)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter

        async with controller.slot("codex"):
            pass

    run(scenario())


def test_timeout_from_slot_body_is_not_reported_as_capacity_error() -> None:
    async def scenario() -> None:
        controller = ConcurrencyController(global_limit=1)
        with pytest.raises(TimeoutError, match="body timeout"):
            async with controller.slot("codex"):
                raise TimeoutError("body timeout")

    run(scenario())


async def _hold_slot(controller: ConcurrencyController) -> None:
    async with controller.slot("codex"):
        await asyncio.sleep(60)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"global_limit": 0}, "global_limit"),
        ({"runner_limits": {"codex": 0}}, "runner"),
        ({"queue_wait_seconds": -1}, "queue"),
    ],
)
def test_controller_rejects_invalid_limits(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ConcurrencyController(**kwargs)
