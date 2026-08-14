# load-bearing

Everyone is trying to make Claude shorter. That is why it is unreadable.

`load-bearing` is a Claude Code plugin that targets how Claude writes, not how
much: unresolved reference, elevated register, and a fixed set of phrases it
reaches for regardless of context. It will sometimes make output *longer*.

It is not one model's problem. Anthropic documents it for Claude Fable 5 under
["Readability when communicating with the user"](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5) —
"dense arrow-chain shorthand, deep implementation detail, references to thinking
the user never saw" — and the Opus 5 and Sonnet 5 guides carry the same register
and verbosity notes. Users report it across the family: "I have had to, with
both Sonnet and Opus 5, ask 'what are you talking about'"; "Opus versions since
4.6 have all had a fair amount of awkward, canned prose."

Opus 5 is where it draws the most complaints, and where the numbers below were
measured. The plugin itself is model-agnostic: an output style is a system
prompt instruction, and the hook is a text check.

## What you get instead

Writing that sounds like a person explaining something to you.

That is the whole target. A colleague who understood the code would tell you
which file broke and what happens now. They would not call it load-bearing, end
on a general truth about software, or point at "the surface" you have never
seen. They would say the thing, in the words people use, and move on.

None of the rules in `output-styles/load-bearing.md` are stylistic preferences.
Each one removes a specific way the model stops sounding like someone talking to
you: reaching for a stock phrase instead of a fact, referring to things you were
never introduced to, using the elevated word where the ordinary one exists.

---

## The problem is not verbosity

Verbosity is the complaint people file, and it is real. One developer ran 163
private eval tasks against Opus 5 and Opus 4.8 on identical prompts and measured
**1.81× the output tokens** (95% CI 1.62–2.02) with **no measurable quality
difference** (−0.018, CI crossing zero).

The interesting part is where the extra tokens landed:

| Task type | Token ratio vs Opus 4.8 |
| --- | --- |
| Factual questions | 2.81× |
| Coding | 2.75× |
| Document Q&A | 2.68× |
| Reasoning | 0.94× |

Reasoning tasks got *shorter*. So this is not a model thinking harder and
spilling it into the answer. In that developer's words: "it does not ramble
because the work is difficult. It turns a one-line answer into a paragraph."

Now look at what the unreadable output actually does:

> That is deliberate and load-bearing rather than tidy.

> which is not a detail: this is the surface you open when name resolution, or
> the fleet, is what is broken.

Both are *compressed*. A metaphor stands in for the claim. A definite article
points at something never introduced. A maxim replaces a fact. These sentences
are shorter than a readable version would be — that is what makes them opaque.

Which means asking for brevity pushes the model further into the failure mode.
Anthropic's own guidance says so:

> the way to keep output short is to be selective about what you include, not to
> compress the writing into fragments, abbreviations, arrow chains, or jargon

Compression is the disease. Most existing tools prescribe more of it.

## What it actually fixes

Three failures, which are usually discussed as one:

**Unresolved reference.** "the surface", "that asymmetry", "this pattern" —
definite reference to things never introduced. The reader reconstructs an
antecedent they were never given. This is why output gets worse deep into a
session: the longer the model works, the more private vocabulary it assumes you
share.

**Metaphor standing in for a claim.** Calling something load-bearing is not
saying what breaks if it is removed.

**A fixed phrasebook.** The same short list recurs across unrelated users and
unrelated codebases: *load-bearing, blast radius, belt and suspenders, seam,
surface area, rough edges, worth noting*. A word that fits everywhere
distinguishes nothing. By the fiftieth use you cannot tell whether something is
genuinely structural or whether that is just the adjective the model reached
for, and you lose the ability to trust its emphasis.

## Why a plugin and not a CLAUDE.md rule

Because `CLAUDE.md` does not hold, and the reason is mechanical.

| | How it works |
| --- | --- |
| `CLAUDE.md` | "Adds a user message after the system prompt" |
| Output style | "Modifies the system prompt … All output styles trigger reminders for Claude to adhere to the output style instructions during the conversation" |

`CLAUDE.md` is a user message near the top of the conversation. As a session
fills with tool results, it gets buried, and nothing re-asserts it. Worse, every
verbose turn becomes an in-context example for the next one, so by turn twenty
the model has twenty demonstrations of the register you asked it to avoid and
one line of instruction. That matches what users report: it works at first, then
reverts after real work happens.

An output style sits in the system prompt and re-triggers adherence reminders
mid-conversation. A hook does not depend on the model choosing to comply at all.

## Layers

| Layer | Mechanism | Guarantee |
| --- | --- | --- |
| `output-styles/load-bearing.md` | System prompt + adherence reminders | Reduces drift. Still an instruction. |
| `scripts/rewrite.py` (Stop hook) | Blocks the turn, feeds back a targeted rewrite instruction | Deterministic. Does not negotiate. |

The hook fires only on detected stock phrasing, names the exact phrases it
found, and asks for the claim underneath each one. It intervenes at most once
per turn, and fails open on any error — a broken hook must never wedge a
session.

## Install

Requires Claude Code ≥ 2.1.91.

```bash
git clone https://github.com/ukanwat/load-bearing
claude --plugin-dir ./load-bearing
```

The output style sets `force-for-plugin: true`, so it applies automatically
whenever the plugin is enabled and overrides your current `outputStyle`. That is
deliberate — an output style you have to remember to select is one you will
forget — but it does mean this takes over the setting while enabled.

### Without the plugin

Copy `output-styles/load-bearing.md` to `~/.claude/output-styles/`, then set
`"outputStyle": "load-bearing"` in your settings. Note that the `/output-style`
command was removed in v2.1.91; use `/config` or edit the setting directly.

## Eval

`eval/` contains an A/B harness. Both arms get an identical copy of a fixture
with a real concurrency bug; the only difference is whether the plugin loads.

```bash
cd eval
./run.sh                 # both arms, all tasks
python3 score.py         # mechanical metrics
python3 score.py --blind # anonymized, key printed last
```

The fixture is a lease-based job queue whose `claim()` has a genuine TOCTOU
race: an `await` on an audit-log call sits between the state check and the
mutation, so two workers can both claim the same job. `AuditLog` buffers 8
records before flushing, and only the flush yields to the event loop, so the
duplicates come out about 8 apart rather than at random.

```
$ cd eval/fixture && python3 verify.py --runs 20
failure rate over 20 runs:
  all_jobs_complete: 0/20
  no_duplicate_processing: 20/20
  failed_job_is_released: 0/20
```

Tasks require reading several files before answering. That is deliberate: a
single-prompt run does not accumulate enough context to reproduce the drift this
plugin exists to fix.

`score.py` measures words, sentence length, stock-phrase rate per 1k words,
dangling references, maxim closers, and em-dashes. It does not measure whether
the technical answer was correct — check that separately.

## Results so far

Honest summary: **one effect is demonstrated, the headline claim is not.**

Fifteen runs on a 450k-line repository, three arms, `claude-opus-5` at `xhigh`,
five runs per arm. The `plain` arm appends one sentence to the prompt — "Write
in plain technical English" — because that is what people already do, and
beating an unmodified baseline would prove nothing.

| arm | words | p90 sentence | stock/1k | em-dash/1k |
| --- | --- | --- | --- | --- |
| none | 1001 ±87 | 38.4 ±6.5 | 1.8 ±0.7 | 14.9 ±3.4 |
| plain | 1222 ±163 | 36.2 ±2.3 | **1.0 ±0.7** | 13.1 ±3.9 |
| plugin | 1046 ±124 | 35.4 ±4.0 | 1.4 ±1.4 | **5.4 ±5.5** |

**Em-dash suppression is real.** Per-run counts barely overlap: plugin
`[3, 9, 12, 1, 1]` against none `[18, 19, 13, 12, 12]`. Roughly 2.5× lower than
either comparison arm.

**Stock phrasing shows no effect**, and `plain` is nominally ahead. The base
rate is only 1–2 phrases per 1000 words in *every* arm, so there is little to
remove in this setting.

A blind pairwise judge (Opus 4.6, presentation order randomized, `plain` vs
`plugin`) scored all six axes within ±0.17 on a 1–5 scale, and split the wins
3–2–1 on readability and 2–2–2 on technical quality. That is a coin flip.

### What that does and does not mean

These were single-turn runs of 77–343 seconds. That is the short-session regime,
and the mechanism this plugin claims does not predict a difference there: at
turn one a prompt instruction and a system-prompt instruction are both fresh.

The claim is about decay. A prompt instruction is one user message near the top
of a conversation; as turns accumulate it gets buried, and the model's own prior
output becomes the in-context example for the next turn. An output style sits in
the system prompt and re-triggers adherence reminders mid-conversation. If that
is right, the arms should be identical at turn 1 and diverge with turn number —
which is exactly the shape of the result above.

`eval/decay.sh` tests that directly: one genuine multi-turn session per arm,
driven through the same task sequence with `--resume`, with an identical
"summarize what you have found so far" prompt repeated at increasing depths.
The measurement is a slope, not a difference of means. Until that runs, the only
claim supported here is em-dash suppression.

## Limits

This is a training default, not a setting. Instructions move it; they do not
remove it. Expect the phrasebook to thin out and reappear late in long sessions,
which is the reason the hook exists.

The output style applies to the main conversation only. A subagent runs its own
system prompt, so it is unaffected. Several users report the jargon compounding
through agents, and this plugin does not currently address that.

## Sources

- [Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5) — Anthropic documents most of these as intended defaults
- [Output styles](https://code.claude.com/docs/en/output-styles)
- [Hooks](https://code.claude.com/docs/en/hooks)
- [Plugins reference](https://code.claude.com/docs/en/plugins-reference)

## License

MIT
