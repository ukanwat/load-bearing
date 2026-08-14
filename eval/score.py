#!/usr/bin/env python3
"""Score eval outputs on the things claudesplain claims to fix.

Every metric here is mechanical and reproducible. None of them measure whether
the technical answer was correct — check that yourself, or use judge.py.

    python3 score.py
    python3 score.py --blind      # anonymize arms, print a shuffled key at the end
"""

import argparse
import pathlib
import random
import re
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hooks"))
import detect  # noqa: E402

OUT = pathlib.Path(__file__).parent / "out"

# Imported rather than copied: two lists would drift, and the scorer would stop
# measuring what the hook enforces.
STOCK_PHRASES = detect.STOCK_PHRASES

# Definite or demonstrative reference to an abstraction the reader cannot locate.
DANGLING_REF = re.compile(
    r"\b(?:the|this|that)\s+"
    r"(?:pattern|asymmetry|tradeoff|trade-off|surface|gap|seam|shape|"
    r"distinction|invariant|contract|tension|subtlety|nuance|wrinkle)\b",
    re.IGNORECASE,
)

# UNRELIABLE — reported but not to be trusted.
#
# Intended to catch a closing flourish that generalises past the evidence. In
# practice it matches any "X not Y" contrast at the end of a sentence, and those
# are usually precise: "it runs as three CLI steps, not one command" is exactly
# the kind of sentence this plugin wants. Measured on real output it produced
# three matches for one arm, all legitimate.
#
# Kept because the count is still worth eyeballing, but do not draw conclusions
# from it without reading the matches. Distinguishing a maxim from a factual
# contrast needs to look at whether the closing clause introduces a claim the
# text never supported, which a regex cannot see.
MAXIM_CLOSER = re.compile(
    r"\b(?:rather than|and not|, not)\b[^.!?\n]{0,60}[.!?]\s*(?:\n|$)",
    re.IGNORECASE,
)

CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)


def prose_only(text: str) -> str:
    """Strip fenced code so metrics measure writing, not diffs."""
    return CODE_BLOCK.sub(" ", text)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 1]


def score(text: str) -> dict:
    prose = prose_only(text)
    words = re.findall(r"\b[\w'-]+\b", prose)
    sents = sentences(prose)
    lengths = [len(re.findall(r"\b[\w'-]+\b", s)) for s in sents] or [0]

    # Same detector the hook uses, so the metric matches what ships.
    flagged, hits, dstats = detect.assess(text)
    stock_hits = dict(hits)
    stock_total = dstats["total"]
    per_1k = dstats["rate_per_1k"]

    return {
        "words": len(words),
        "sentences": len(sents),
        "mean_sentence": round(statistics.mean(lengths), 1),
        "p90_sentence": round(sorted(lengths)[int(len(lengths) * 0.9) - 1], 1)
        if len(lengths) > 1 else lengths[0],
        "stock_total": stock_total,
        "stock_per_1k_words": round(per_1k, 2),
        "would_flag": "yes" if flagged else "",
        "stock_detail": {k: v for k, v in stock_hits.items() if v},
        "dangling_refs": len(DANGLING_REF.findall(prose)),
        "maxim_closers": len(MAXIM_CLOSER.findall(prose)),
        "em_dashes": prose.count("—"),
    }


COLUMNS = [
    ("words", "words"),
    ("mean_sentence", "mean sent"),
    ("p90_sentence", "p90 sent"),
    ("stock_total", "stock"),
    ("stock_per_1k_words", "stock/1k"),
    ("would_flag", "hook?"),
    ("dangling_refs", "dangling"),
    ("maxim_closers", "maxims"),
    ("em_dashes", "em-dash"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blind", action="store_true")
    args = parser.parse_args()

    files = sorted(OUT.glob("*.md"))
    if not files:
        print(f"no outputs in {OUT} — run ./run.sh first", file=sys.stderr)
        return 1

    rows = []
    for path in files:
        stem = path.stem
        task, _, arm = stem.rpartition("__")
        rows.append({
            "task": task or stem,
            "arm": arm or "?",
            "file": path.name,
            **score(path.read_text(encoding="utf-8")),
        })

    labels = {}
    if args.blind:
        tags = [f"sample-{c}" for c in "ABCDEFGH"]
        random.shuffle(tags)
        for row, tag in zip(rows, tags):
            labels[tag] = f"{row['task']} / {row['arm']}"
            row["arm"] = tag
        rows.sort(key=lambda r: r["arm"])

    header = f"{'task':<28} {'arm':<12}" + "".join(f"{h:>11}" for _, h in COLUMNS)
    print(header)
    print("-" * len(header))
    for row in rows:
        task = row["task"] if not args.blind else ""
        line = f"{task:<28} {row['arm']:<12}"
        line += "".join(f"{row[k]:>11}" for k, _ in COLUMNS)
        print(line)

    if not args.blind:
        print()
        for row in rows:
            if row["stock_detail"]:
                print(f"{row['file']}: {row['stock_detail']}")
    else:
        print("\nkey:")
        for tag in sorted(labels):
            print(f"  {tag} = {labels[tag]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
