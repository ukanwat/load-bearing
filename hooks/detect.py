"""Stock-phrase detection, shared by the Stop hook and the eval scorer.

The failure this targets is recurrence, not vocabulary. One "surface area" in a
page of prose is ordinary English. Four stock phrases in one message is a
phrasebook. Detecting presence flags correct writing; detecting density does
not.

Thresholds are calibrated in tests/test_detect.py against a corpus of
legitimate technical prose (must stay silent) and one of observed slop (must
fire).
"""

import re

# Phrases observed recurring across unrelated users, codebases, and tasks.
# Several have legitimate uses, which is why presence alone never triggers.
STOCK_PHRASES = [
    "load-bearing",
    "load bearing",
    "blast radius",
    "belt and suspenders",
    "belt-and-suspenders",
    "rough edges",
    "surface area",
    "the seam",
    # Bare "seams" is deliberately absent: it is literal in graphics, geology,
    # and manufacturing -- "chunks cannot disagree at their seams" is correct
    # writing -- and including it produced false hits on real output.
    "worth knowing",
    "worth noting",
    "the tradeoff here",
    "in practice this means",
    "deliberate rather than",
    "rather than tidy",
    "not quite",
]

# Calibrated in eval/test_detect.py. On that corpus, legitimate technical prose
# peaks at 30 hits per 1k words while phrasebook prose starts at 82, so rate is
# the discriminating signal. Distinct count is not: a correct 244-word document
# reached 5 distinct phrases, and the phrasebook samples start at 6.
#
# The threshold sits nearer the legitimate ceiling than the phrasebook floor on
# purpose. A false positive forces a rewrite of writing that was already fine,
# which is worse than missing a message the output style may have already
# improved.
#
# The corpus is small and hand-written. Re-tune against real outputs in eval/out
# before trusting these numbers on long messages, where rate falls as length
# grows even when the habit persists. REPEAT_LIMIT is the length-independent
# guard for exactly that case.

# Below this, a message is too short for density to mean anything.
MIN_WORDS = 60
# One phrase repeated this often is a tic at any length.
REPEAT_LIMIT = 3
# Otherwise require both several distinct phrases and a high rate.
MIN_DISTINCT = 3
MIN_RATE_PER_1K = 50.0

CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]+`")


def prose_only(text):
    """Strip code so identifiers and diffs cannot trip the detector."""
    text = CODE_BLOCK.sub(" ", text)
    return INLINE_CODE.sub(" ", text)


def find_stock(text):
    """Return [(phrase, count)] for stock phrases in the prose portion of text.

    Whitespace is collapsed first: wrapped output splits phrases across
    newlines, and "blast\\nradius" must still count as a hit.
    """
    lowered = re.sub(r"\s+", " ", prose_only(text)).lower()
    hits = []
    for phrase in STOCK_PHRASES:
        count = len(re.findall(r"\b" + re.escape(phrase) + r"\b", lowered))
        if count:
            hits.append((phrase, count))
    return hits


def word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", prose_only(text)))


def assess(text):
    """Decide whether text shows the phrasebook pattern.

    Returns (should_flag, hits, stats).
    """
    hits = find_stock(text)
    words = word_count(text)
    total = sum(count for _, count in hits)
    distinct = len(hits)
    rate = (total / words * 1000) if words else 0.0
    stats = {"words": words, "total": total, "distinct": distinct,
             "rate_per_1k": round(rate, 2)}

    if not hits or words < MIN_WORDS:
        return False, hits, stats
    if any(count >= REPEAT_LIMIT for _, count in hits):
        return True, hits, stats
    if distinct >= MIN_DISTINCT and rate >= MIN_RATE_PER_1K:
        return True, hits, stats
    return False, hits, stats
