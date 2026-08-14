#!/usr/bin/env python3
"""Zero-dependency checks for the job queue.

check_no_duplicate_processing fails on every run measured so far (20/20). The
duplicated job indices come out roughly 8 apart, which is the tell: AuditLog
buffers 8 records before flushing, and only the flush yields to the event loop.

    python3 verify.py            # one run
    python3 verify.py --runs 20  # repeat, report failure rate
"""

import argparse
import asyncio
import sys

from jobq.store import Job, JobStore
from jobq.worker import WorkerPool


def make_store(n: int = 40) -> JobStore:
    store = JobStore(lease_seconds=30.0)
    for i in range(n):
        store.put(Job(id=f"job-{i}", payload={"n": i}))
    return store


async def check_all_jobs_complete() -> None:
    store = make_store()
    seen = []

    async def handler(payload):
        seen.append(payload["n"])
        await asyncio.sleep(0)

    pool = WorkerPool(store, handler, size=4)
    await pool.run(max_iterations=60)
    await asyncio.sleep(0.05)

    assert len(seen) >= 40, f"only {len(seen)} of 40 jobs ran"


async def check_no_duplicate_processing() -> None:
    store = make_store()
    seen = []

    async def handler(payload):
        await asyncio.sleep(0)
        seen.append(payload["n"])

    pool = WorkerPool(store, handler, size=4)
    await pool.run(max_iterations=60)
    await asyncio.sleep(0.05)

    dupes = sorted({n for n in seen if seen.count(n) > 1})
    assert not dupes, f"processed more than once: {dupes}"


async def check_failed_job_is_released() -> None:
    store = make_store(n=1)

    async def handler(payload):
        raise RuntimeError("handler blew up")

    pool = WorkerPool(store, handler, size=1)
    await pool.run(max_iterations=5)
    await asyncio.sleep(0.1)

    job = store.get("job-0")
    assert job.state == "pending", f"expected pending, got {job.state}"


CHECKS = [
    ("all_jobs_complete", check_all_jobs_complete),
    ("no_duplicate_processing", check_no_duplicate_processing),
    ("failed_job_is_released", check_failed_job_is_released),
]


async def run_once(quiet: bool = False) -> dict:
    results = {}
    for name, fn in CHECKS:
        try:
            await fn()
            results[name] = None
        except AssertionError as exc:
            results[name] = str(exc)
        except Exception as exc:  # noqa: BLE001
            results[name] = f"{type(exc).__name__}: {exc}"
        if not quiet:
            status = "PASS" if results[name] is None else "FAIL"
            detail = "" if results[name] is None else f"  {results[name]}"
            print(f"[{status}] {name}{detail}")
    return results


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()

    if args.runs == 1:
        results = await run_once()
        return 1 if any(v is not None for v in results.values()) else 0

    failures = {name: 0 for name, _ in CHECKS}
    for _ in range(args.runs):
        results = await run_once(quiet=True)
        for name, err in results.items():
            if err is not None:
                failures[name] += 1

    print(f"failure rate over {args.runs} runs:")
    for name, count in failures.items():
        print(f"  {name}: {count}/{args.runs}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
