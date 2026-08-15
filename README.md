# claudesplain

> **claudesplain** *(verb)* — to explain something at length, entirely
> correctly, in words the listener has never encountered, while assuming they
> watched you arrive at it.

Your agent worked for two hours. It comes back and says:

```
The retry path is the load-bearing piece here. That asymmetry is what bites you, and the blast radius is small.
                      ^                        ^                                         ^
                      what breaks?             between what and what?                    affecting whom?
```

Every word is ordinary English. Nothing is wrong. You still can't act on it.

Each of those three phrases points at something the model knows and you don't.
It read the code, so *it* knows which retry path, which two things differ, and
who is affected. It wrote the sentence for the version of you that read the code
too.

**That version of you does not exist.** That's the bug.

What it meant:

```diff
- The retry path is the load-bearing piece here.
- That asymmetry is what bites you, and the blast radius is small.
+ Mobile retries a failed payment after 3 seconds. Web waits 30.
+ When the payment API is slow, mobile can charge the same card 10 times.
+ Only the mobile constant needs changing.
```

Everyone else is trying to make Claude *shorter*. That's why it's unreadable —
the first version is already the compressed one. "load-bearing" is shorter than
"charges the card ten times," and squeezing harder is what produced it.

`claudesplain` targets how Claude writes, not how much.

Length is not the lever, and it moves with the content rather than in a fixed
direction. Over five runs per arm on the same repository: unmodified 1001 words,
with a plain-English prompt 1222, with this plugin 1046. It does not pad and it
does not promise brevity.

What it changes is which of the two ways to be shorter Claude reaches for:

| | |
|---|---|
| **Cut** | drop whole items the reader doesn't need → shorter *and* clearer |
| **Compress** | squeeze a sentence into jargon and fragments → shorter and *unreadable* |

"load-bearing" is four words shorter than "publish breaks if you remove it."
That's compression, and it's where the unreadability comes from — which is why
telling Claude to be concise makes this worse, not better. Every tool in this
category asks for exactly the thing that caused the problem.

`claudesplain` asks for the other one: cut the process narration, the caveats
about things that cannot happen, the summary of the summary — then write what
survives properly.

## The first sentence

You sent someone off to figure out how the auth system works. They come back.

Illustrations, not transcripts — but the shape is what changes:

**Before:**

> I went through the auth module, the session store, and the middleware chain,
> plus the tests. Here's how it works.

**After:**

> Sessions are JWTs signed with one shared secret, checked by middleware on
> every request, and refreshed by a cron job an hour before they expire.

The first sentence is about the worker. It reports effort — what was opened, how
much ground was covered — and asks you to wait one more sentence before anything
you can use. You did not ask what it read.

The second is about the thing you asked about. Three facts, no preamble.

This is the single most common shape in a long agent session, and it costs you a
sentence every time.

---

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

Someone who keeps track of what you have actually seen.

That is the whole target, and it is a harder thing than sounding plain. A good
colleague reporting back knows which files you have open and which you have
never heard of, that you were in a meeting for the last hour, that the name they
invented for a pattern at 2pm means nothing to you. So they introduce things
before referring to them, and hand you a report that stands on its own.

Claude does not track that by default. It writes as though you were sitting
behind it the whole time: definite reference to things it never introduced
("the surface", "that asymmetry"), shorthand it built up while working, detail
that only makes sense if you watched it happen. The information is usually all
correct. It is addressed to a participant, and you were not one.

This is also why it gets worse the longer a session runs. More private
vocabulary accumulates, and more of it leaks into text meant for you.

Every rule in `output-styles/claudesplain.md` is a mechanical form of the same
instruction — assume the reader was not there:

| rule | what it enforces |
| --- | --- |
| No `the` on a noun you have not introduced | the reader can identify every referent |
| Write the claim, not the metaphor | "load-bearing" tells them nothing; what breaks does |
| No stock phrase for emphasis | if it matters, say what goes wrong without it |
| Prefer the common word | they should not have to decode vocabulary |
| Longer is fine | completeness beats compression |

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
| `output-styles/claudesplain.md` | System prompt + adherence reminders | Reduces drift. Still an instruction. |
| `scripts/rewrite.py` (Stop hook) | Blocks the turn, feeds back a targeted rewrite instruction | Deterministic. Does not negotiate. |

The hook fires only on detected stock phrasing, names the exact phrases it
found, and asks for the claim underneath each one. It intervenes at most once
per turn, and fails open on any error — a broken hook must never wedge a
session.

## Install

Requires Claude Code ≥ 2.1.91.

```bash
git clone https://github.com/ukanwat/claudesplain
claude --plugin-dir ./claudesplain
```

The output style sets `force-for-plugin: true`, so it applies automatically
whenever the plugin is enabled and overrides your current `outputStyle`. That is
deliberate — an output style you have to remember to select is one you will
forget — but it does mean this takes over the setting while enabled.

### Without the plugin

Copy `output-styles/claudesplain.md` to `~/.claude/output-styles/`, then set
`"outputStyle": "claudesplain"` in your settings. Note that the `/output-style`
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

Three arms: unmodified, a plain-English prompt, and the plugin. The middle one
matters — beating an unmodified baseline proves nothing when one sentence in the
prompt already helps.

`score.py` measures words, sentence length, stock-phrase rate, dangling
references, and em-dashes. It does not check whether the technical answer was
correct.

`decay.sh` drives one multi-turn session per arm through the same task sequence,
repeating an identical summarize prompt at increasing depths, and scores the
slope. That is the measurement that matters for long sessions.

## Measurements

Five runs per arm, `claude-opus-5` at `xhigh`, on a 450k-line repository.

| arm | words | p90 sentence | stock/1k | em-dash/1k |
| --- | --- | --- | --- | --- |
| none | 1001 ±87 | 38.4 ±6.5 | 1.8 ±0.7 | 14.9 ±3.4 |
| plain | 1222 ±163 | 36.2 ±2.3 | 1.0 ±0.7 | 13.1 ±3.9 |
| plugin | 1046 ±124 | 35.4 ±4.0 | 1.4 ±1.4 | **5.4 ±5.5** |

Em-dash rate drops about 2.5× against both comparison arms, and the per-run
counts barely overlap: `[3, 9, 12, 1, 1]` against `[18, 19, 13, 12, 12]`.

Stock-phrase rate shows no separation at this base rate — 1–2 per thousand words
in every arm, including unmodified.

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
