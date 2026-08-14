"""Worker pool that drains a JobStore."""

import asyncio
from typing import Callable, Optional

from .scheduler import RetryScheduler
from .store import Job, JobStore


class Worker:
    def __init__(
        self,
        worker_id: str,
        store: JobStore,
        handler: Callable,
        scheduler: Optional[RetryScheduler] = None,
        poll_interval: float = 0.01,
    ):
        self.worker_id = worker_id
        self.store = store
        self.handler = handler
        self.scheduler = scheduler or RetryScheduler()
        self.poll_interval = poll_interval
        self.processed = 0
        self._running = False

    async def run(self, max_iterations: int = 100) -> None:
        self._running = True
        for _ in range(max_iterations):
            if not self._running:
                break

            job = await self.store.claim(self.worker_id)
            if job is None:
                await asyncio.sleep(self.poll_interval)
                continue

            asyncio.create_task(self._process(job))

        await asyncio.sleep(self.poll_interval)

    async def _process(self, job: Job) -> None:
        try:
            result = self.handler(job.payload)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            delay = self.scheduler.next_delay(job)
            await asyncio.sleep(delay)
            await self.store.release(job.id, self.worker_id)
            return

        await self.store.complete(job.id, self.worker_id)
        self.processed += 1

    def stop(self) -> None:
        self._running = False


class WorkerPool:
    def __init__(self, store: JobStore, handler: Callable, size: int = 4):
        self.workers = [
            Worker(f"w{i}", store, handler) for i in range(size)
        ]

    async def run(self, max_iterations: int = 100) -> None:
        await asyncio.gather(
            *(w.run(max_iterations) for w in self.workers)
        )

    @property
    def processed(self) -> int:
        return sum(w.processed for w in self.workers)
