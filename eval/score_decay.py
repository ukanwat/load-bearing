#!/usr/bin/env python3
"""Score a long-session run and look for drift with turn number.

run.sh answers "is arm A better than arm B on one turn." This answers the
question that actually matters: does an instruction delivered once still hold
fifteen turns later, when the model's own output has become the dominant
context?

The turns file repeats an identical prompt -- "Summarize what you have found so
far." -- at increasing depths. Those turns are the measurement: same request,
same arm, more accumulated context. Everything between them is there to build
that context.

A flat line means the instruction held. An upward slope on stock phrasing or
em-dashes means it decayed.

    python3 score_decay.py
    python3 score_decay.py --metric em_per_1k
"""

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hooks"))
import detect  # noqa: E402

OUT = pathlib.Path(__file__).parent / "out-decay"
RECAP = "summarize what you have found so far"
MIN_WORDS = 20

METRICS = ["stock_per_1k", "em_per_1k", "mean_sentence", "words"]


def measure(text):
    prose = detect.prose_only(text)
    words = re.findall(r"\b[\w'-]+\b", prose)
    sents = [s for s in re.split(r"(?<=[.!?])\s+", prose) if len(s.strip()) > 1]
    lengths = [len(re.findall(r"\b[\w'-]+\b", s)) for s in sents] or [0]
    _flag, _hits, stats = detect.assess(text)
    n = len(words) or 1
    return {
        "words": len(words),
        "mean_sentence": round(sum(lengths) / len(lengths), 1),
        "stock_per_1k": stats["rate_per_1k"],
        "em_per_1k": round(prose.count("—") / n * 1000, 1),
    }


def load(turns_file):
    """Return {arm: {turn: metrics}} and the set of recap turn numbers."""
    recap_turns = set()
    if turns_file.exists():
        i = 0
        for line in turns_file.read_text().splitlines():
            if not line.strip():
                continue
            i += 1
            if RECAP in line.strip().lower():
                recap_turns.add(i)

    data = {}
    for path in sorted(OUT.glob("*.md")):
        m = re.match(r"(.+)__turn(\d+)$", path.stem)
        if not m:
            continue
        arm, turn = m.group(1), int(m.group(2))
        text = path.read_text(encoding="utf-8").strip()
        if len(text.split()) < MIN_WORDS:
            continue
        data.setdefault(arm, {})[turn] = measure(text)
    return data, recap_turns


def slope(points):
    """Least-squares slope of y over x. Positive means drift upward."""
    if len(points) < 2:
        return None
    n = len(points)
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    return (n * sxy - sx * sy) / denom


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric", default="stock_per_1k", choices=METRICS)
    parser.add_argument("--turns-file", default="turns-repo.txt")
    args = parser.parse_args()

    data, recap_turns = load(pathlib.Path(__file__).parent / args.turns_file)
    if not data:
        print(f"no outputs in {OUT} — run ./decay.sh first", file=sys.stderr)
        return 1

    metric = args.metric
    all_turns = sorted({t for turns in data.values() for t in turns})

    print(f"metric: {metric}   (recap turns marked *)\n")
    header = "turn  " + "".join(f"{a:>12}" for a in sorted(data))
    print(header)
    print("-" * len(header))
    for t in all_turns:
        mark = "*" if t in recap_turns else " "
        row = f"{t:>3}{mark}  "
        for arm in sorted(data):
            v = data[arm].get(t, {}).get(metric)
            row += f"{v:>12}" if v is not None else f"{'-':>12}"
        print(row)

    print("\nslope over all turns (positive = drifting worse)")
    for arm in sorted(data):
        pts = [(t, m[metric]) for t, m in sorted(data[arm].items())]
        s = slope(pts)
        print(f"  {arm:<8} {s:+.3f} per turn" if s is not None else f"  {arm:<8} n/a")

    if recap_turns:
        print("\nrecap turns only — identical prompt, increasing context")
        for arm in sorted(data):
            pts = [(t, m[metric]) for t, m in sorted(data[arm].items())
                   if t in recap_turns]
            if not pts:
                continue
            vals = ", ".join(f"t{t}={v}" for t, v in pts)
            s = slope(pts)
            tail = f"   slope {s:+.3f}" if s is not None else ""
            print(f"  {arm:<8} {vals}{tail}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
