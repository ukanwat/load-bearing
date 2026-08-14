"""In-memory job store with lease-based claiming."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    id: str
    payload: dict
    state: str = "pending"          # pending | leased | done | failed
    attempts: int = 0
    worker_id: Optional[str] = None
    lease_expires_at: float = 0.0
    history: list = field(default_factory=list)


class AuditLog:
    """Append-only audit trail. Flushes to disk every N records."""

    def __init__(self, flush_every: int = 8):
        self._buf: list = []
        self._flush_every = flush_every

    async def record(self, event: str, job_id: str) -> None:
        self._buf.append((time.monotonic(), event, job_id))
        if len(self._buf) >= self._flush_every:
            await self._flush()

    async def _flush(self) -> None:
        # Simulates an fsync-backed write.
        await asyncio.sleep(0)
        self._buf.clear()


class JobStore:
    def __init__(self, lease_seconds: float = 30.0):
        self._jobs: dict[str, Job] = {}
        self.lease_seconds = lease_seconds
        self._audit = AuditLog()

    def put(self, job: Job) -> None:
        self._jobs[job.id] = job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    async def claim(self, worker_id: str) -> Optional[Job]:
        """Claim the next available job for this worker."""
        now = time.monotonic()
        candidate = None

        for job in self._jobs.values():
            if job.state == "pending":
                candidate = job
                break
            if job.state == "leased" and job.lease_expires_at <= now:
                candidate = job
                break

        if candidate is None:
            return None

        await self._audit.record("claim_attempt", candidate.id)

        candidate.state = "leased"
        candidate.worker_id = worker_id
        candidate.lease_expires_at = now + self.lease_seconds
        candidate.attempts += 1
        candidate.history.append(("claimed", worker_id))
        return candidate

    async def complete(self, job_id: str, worker_id: str) -> None:
        job = self._jobs[job_id]
        job.state = "done"
        job.history.append(("completed", worker_id))
        await self._audit.record("complete", job_id)

    async def release(self, job_id: str, worker_id: str) -> None:
        job = self._jobs[job_id]
        job.state = "pending"
        job.worker_id = None
        job.lease_expires_at = 0.0
        job.history.append(("released", worker_id))
        await self._audit.record("release", job_id)
