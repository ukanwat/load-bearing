#!/usr/bin/env python3
"""Calibration for the stock-phrase detector.

Two corpora, opposite requirements:

  LEGITIMATE -- correct technical prose that happens to use these words. Every
                one of these must pass unflagged. A detector that fires here
                makes the plugin actively harmful, forcing rewrites of writing
                that was already fine.

  PHRASEBOOK -- the pattern this plugin exists to catch: several stock phrases
                carrying the weight of claims the text never states. Every one
                must be flagged.

Run: python3 test_detect.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hooks"))
import detect  # noqa: E402


LEGITIMATE = [
    # Each uses a listed phrase correctly, in prose that says something specific.
    """The retry path is not quite idempotent. `RetryScheduler.next_delay` reads
    `job.attempts`, but `claim()` increments that counter before the handler
    runs, so a job that fails twice backs off as though it had failed three
    times. The practical effect is that the fifth retry waits 80ms instead of
    40ms. That is tolerable here, but it means the backoff curve in the
    dashboard does not match the one in the code, and anyone tuning
    `base_delay` from that graph will be off by one doubling.""",

    """Reducing the public API surface area from 40 methods to 12 cut the
    migration cost for downstream teams. We kept `claim`, `complete`, and
    `release` and moved everything else behind an internal module. Two callers
    depended on `JobStore._jobs` directly, so we added an explicit `snapshot()`
    rather than break them. The seam between storage and scheduling is now a
    single interface, which is what made the Postgres backend possible without
    touching worker code.""",

    """It is worth noting that PostgreSQL stores oversized tuples out of line
    once a row exceeds roughly 2KB, not 8KB as the page size suggests. The
    threshold is `TOAST_TUPLE_THRESHOLD`, and rows above it get compressed
    before they are moved. This changed the write amplification we measured on
    the audit table: rows averaged 2.4KB, so almost every insert triggered a
    TOAST write we had not accounted for in the capacity model.""",

    # Long-form legitimate writing. This is the dangerous case: real technical
    # documents run to hundreds of words and naturally accumulate several of
    # these terms without any of them standing in for a claim.
    """We moved the queue from in-memory storage to Postgres over three weeks.
    The first decision was where to put the seam. Storage and scheduling were
    already separate classes, but `Worker._process` reached into `JobStore`
    twice for things it could have been handed, so we passed those in and left
    the interface at three methods.

    Reducing the surface area mattered more than it usually does here, because
    the Postgres implementation has to hold a transaction open across the same
    calls. Four methods would have meant a second round trip on the hot path.

    The lease logic is not quite the same between the two backends. In memory,
    an expired lease is reclaimed by whichever worker notices first. In
    Postgres we use `SELECT ... FOR UPDATE SKIP LOCKED`, so the database picks,
    and the order differs under contention. Job ordering is not part of the
    contract, so this is allowed, but it did change which jobs failed first in
    our load test and cost an afternoon of confusion.

    It is worth noting that the migration is reversible for exactly one
    release. Both backends write the same audit records, so you can switch back
    by changing one config value. After the next release that stops being true,
    because the new schema drops the columns the in-memory path reads. There
    are rough edges around the reversal path we have not tested: the audit
    buffer is not flushed on shutdown, so a switch under load loses up to eight
    records. We accepted that rather than block the migration.""",
]

PHRASEBOOK = [
    # Several stock phrases doing the work of claims the text never makes.
    """The audit flush is load-bearing here, and that is deliberate rather than
    tidy. Worth noting that the blast radius stays small: the seam between
    claim and complete absorbs it. This is a belt and suspenders arrangement
    rather than a single guarantee, and the surface area you expose is the
    thing that matters when the fleet is what is broken. There are rough edges
    worth knowing about before you rely on it in production.""",

    """Kestrel comes in as a framework reference, not a package, and that is
    deliberate rather than tidy. One rule applied twice: the product gets the
    well-known port and management moves aside. Above 1024, so its unit needs
    no capability at all, which is not a detail: this is the surface area you
    open when name resolution is what is broken. The blast radius is small but
    the rough edges are worth knowing about.""",
]

SHORT_BUT_STOCKY = [
    # Under MIN_WORDS. Too little text to judge density; must not fire.
    "The audit flush is load-bearing. Worth noting the blast radius is small.",
]


def run():
    failures = 0

    print("LEGITIMATE (must NOT flag)")
    for i, text in enumerate(LEGITIMATE):
        flag, hits, stats = detect.assess(text)
        status = "FAIL" if flag else "ok"
        if flag:
            failures += 1
        print(f"  [{status:4}] #{i} words={stats['words']:3} "
              f"distinct={stats['distinct']} rate={stats['rate_per_1k']:5} "
              f"{[h[0] for h in hits]}")

    print("\nPHRASEBOOK (must flag)")
    for i, text in enumerate(PHRASEBOOK):
        flag, hits, stats = detect.assess(text)
        status = "ok" if flag else "FAIL"
        if not flag:
            failures += 1
        print(f"  [{status:4}] #{i} words={stats['words']:3} "
              f"distinct={stats['distinct']} rate={stats['rate_per_1k']:5} "
              f"{[h[0] for h in hits]}")

    print("\nTOO SHORT TO JUDGE (must NOT flag)")
    for i, text in enumerate(SHORT_BUT_STOCKY):
        flag, hits, stats = detect.assess(text)
        status = "FAIL" if flag else "ok"
        if flag:
            failures += 1
        print(f"  [{status:4}] #{i} words={stats['words']:3} "
              f"distinct={stats['distinct']} rate={stats['rate_per_1k']:5}")

    total = len(LEGITIMATE) + len(PHRASEBOOK) + len(SHORT_BUT_STOCKY)
    print(f"\n{total - failures}/{total} passed")
    print(f"thresholds: MIN_WORDS={detect.MIN_WORDS} "
          f"REPEAT_LIMIT={detect.REPEAT_LIMIT} "
          f"MIN_DISTINCT={detect.MIN_DISTINCT} "
          f"MIN_RATE_PER_1K={detect.MIN_RATE_PER_1K}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
