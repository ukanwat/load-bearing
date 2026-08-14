"""Retry backoff policy."""

import random

from .store import Job


class RetryScheduler:
    def __init__(
        self,
        base_delay: float = 0.005,
        max_delay: float = 1.0,
        max_attempts: int = 5,
        jitter: bool = True,
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts
        self.jitter = jitter

    def next_delay(self, job: Job) -> float:
        """Exponential backoff based on how many times this job has been tried."""
        exponent = max(job.attempts - 1, 0)
        delay = self.base_delay * (2 ** exponent)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = delay * random.uniform(0.5, 1.0)
        return delay

    def should_retry(self, job: Job) -> bool:
        return job.attempts < self.max_attempts
