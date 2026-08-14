#!/usr/bin/env python3
"""Blind pairwise judge for eval outputs.

Pairs baseline against treated for the same task, strips arm labels, randomizes
which is presented first, and asks a *different* model to compare them. Judging
with the same model that produced the text invites self-preference.

The default judge is Opus 4.6. It predates the register shift this plugin exists
to undo, and users who tuned Opus 5 successfully described the result as
"communicates more like 4.6" — so it is the closest thing available to the
target the plugin aims at, rather than a peer of the model under test.

The judge scores readability and, separately, whether the technical content
survived. A style intervention that improves prose while degrading the analysis
is a failure, and only a correctness check catches that.

    python3 judge.py
    python3 judge.py --judge-model claude-sonnet-5 --reps 3
"""

import argparse
import json
import pathlib
import random
import re
import subprocess
import sys
from collections import defaultdict

OUT = pathlib.Path(__file__).parent / "out"

RUBRIC = """You are comparing two answers to the same deep technical question about a \
concurrency bug. Judge them on how they are written and on whether the technical \
content is intact.

Score each sample 1-5 on each axis. Be strict; do not award ties out of politeness.

READABILITY AXES
1. resolved_reference: Does it name what it refers to? Penalize definite or \
demonstrative reference to things never introduced ("the surface", "that \
asymmetry", "this pattern") where the reader cannot identify the antecedent.
2. plain_register: Does it use the common word where one exists? Penalize \
elevated or abstract phrasing that obscures a simple claim.
3. concrete_claims: Does it state what happens, or does a metaphor stand in for \
the claim? Penalize figures of speech doing the work of a fact.
4. no_stock_phrasing: Penalize fixed phrases used for emphasis, such as \
"load-bearing", "blast radius", "belt and suspenders", "worth noting", "surface \
area", "rough edges".

CORRECTNESS AXES
5. technical_depth: Does it identify the actual race, the specific interleaving, \
and the mechanism? More detail scores higher only if it is correct and relevant.
6. technical_accuracy: Are the claims true and specific to this code? Penalize \
vagueness, hedging, and anything that reads as invented.

Then pick an overall winner for READABILITY and, separately, for TECHNICAL \
QUALITY. The winner may differ on each.

Respond with ONLY a JSON object, no prose, no code fence:
{"sample_1": {"resolved_reference": n, "plain_register": n, "concrete_claims": n, \
"no_stock_phrasing": n, "technical_depth": n, "technical_accuracy": n}, \
"sample_2": {...}, "readability_winner": "sample_1"|"sample_2"|"tie", \
"technical_winner": "sample_1"|"sample_2"|"tie", "note": "one sentence"}"""


# A failed run still writes a short line to its .md file — "You've hit your
# session limit", a permission refusal — and the judge will dutifully score two
# error messages against each other and call it a tie. Anything this short is
# not an answer.
MIN_WORDS = 20


def load_pairs(arm_a, arm_b):
    pairs = defaultdict(dict)
    for path in OUT.glob("*.md"):
        task, _, arm = path.stem.rpartition("__")
        text = path.read_text(encoding="utf-8").strip()
        if len(text.split()) >= MIN_WORDS:
            pairs[task][arm] = (path.name, text)
    return {k: v for k, v in pairs.items() if arm_a in v and arm_b in v}


def ask_judge(model, sample_1, sample_2):
    prompt = (
        f"{RUBRIC}\n\n"
        f"=== SAMPLE 1 ===\n{sample_1}\n\n"
        f"=== SAMPLE 2 ===\n{sample_2}\n"
    )
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", model,
         "--allowedTools", "", "--output-format", "text"],
        capture_output=True, text=True, timeout=900,
    )
    if proc.returncode != 0:
        return None, proc.stderr[-300:]

    raw = proc.stdout.strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None, f"no JSON in judge reply: {raw[:200]}"
    try:
        return json.loads(match.group(0)), None
    except json.JSONDecodeError as exc:
        return None, f"bad JSON: {exc}"


AXES = ["resolved_reference", "plain_register", "concrete_claims",
        "no_stock_phrasing", "technical_depth", "technical_accuracy"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge-model", default="claude-opus-4-6")
    parser.add_argument("--reps", type=int, default=1,
                        help="judgements per pair; order is re-randomized each time")
    # plain vs plugin is the decisive comparison: beating an unmodified baseline
    # proves little when one sentence in the prompt already helps.
    parser.add_argument("--a", dest="arm_a", default="plain")
    parser.add_argument("--b", dest="arm_b", default="plugin")
    args = parser.parse_args()

    arm_a, arm_b = args.arm_a, args.arm_b
    pairs = load_pairs(arm_a, arm_b)
    if not pairs:
        print(f"no complete {arm_a}/{arm_b} pairs in out/", file=sys.stderr)
        return 1

    totals = {arm_a: defaultdict(list), arm_b: defaultdict(list)}
    wins = {"readability": defaultdict(int), "technical": defaultdict(int)}

    for task, arms in sorted(pairs.items()):
        for rep in range(args.reps):
            # Randomize presentation order so position cannot drive the verdict.
            order = [arm_a, arm_b]
            random.shuffle(order)
            first, second = order

            verdict, err = ask_judge(
                args.judge_model, arms[first][1], arms[second][1]
            )
            if verdict is None:
                print(f"  {task} rep{rep}: judge failed — {err}")
                continue

            slot = {"sample_1": first, "sample_2": second}
            for key, arm in slot.items():
                scores = verdict.get(key, {})
                for axis in AXES:
                    if isinstance(scores.get(axis), (int, float)):
                        totals[arm][axis].append(scores[axis])

            for kind, field in (("readability", "readability_winner"),
                                ("technical", "technical_winner")):
                winner = verdict.get(field)
                wins[kind][slot.get(winner, "tie")] += 1

            print(f"  {task} rep{rep}: readability -> "
                  f"{slot.get(verdict.get('readability_winner'), 'tie')}, "
                  f"technical -> "
                  f"{slot.get(verdict.get('technical_winner'), 'tie')}")
            if verdict.get("note"):
                print(f"    {verdict['note']}")

    print(f"\njudge: {args.judge_model}   ({arm_a} vs {arm_b})")
    print(f"{'axis':<22}{arm_a:>10}{arm_b:>10}{'delta':>10}")
    print("-" * 52)
    for axis in AXES:
        a_scores = totals[arm_a][axis]
        b_scores = totals[arm_b][axis]
        if not a_scores or not b_scores:
            continue
        am = sum(a_scores) / len(a_scores)
        bm = sum(b_scores) / len(b_scores)
        print(f"{axis:<22}{am:>10.2f}{bm:>10.2f}{bm - am:>+10.2f}")

    print("\nwins")
    for kind in ("readability", "technical"):
        counts = wins[kind]
        print(f"  {kind:<12} {arm_a}={counts[arm_a]} "
              f"{arm_b}={counts[arm_b]} tie={counts['tie']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
