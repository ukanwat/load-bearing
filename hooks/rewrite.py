#!/usr/bin/env python3
"""Stop hook: catch the phrasebook pattern and require one rewrite.

The output style asks the model to avoid a fixed vocabulary. This checks whether
it did. Instructions drift as a session accumulates context; a hook does not.

Contract (see https://code.claude.com/docs/en/hooks):
  - exit 0 -> allow the turn to end
  - exit 2 -> block the stop, stderr is fed back to Claude as the instruction

The Stop payload provides `last_assistant_message` (a string) and
`stop_hook_active` (true when this hook already blocked once this turn).
Transcript parsing is a fallback for payloads that omit the message.

Detection is density-based, not presence-based — see detect.py. Fails open: any
error allows the stop, because a broken hook must never wedge a session.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect  # noqa: E402


def transcript_fallback(transcript_path):
    """Read the last assistant message from a transcript, or '' if unreadable."""
    if not transcript_path:
        return ""
    try:
        with open(transcript_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return ""

    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        message = entry.get("message") or {}
        if (message.get("role") or entry.get("type")) != "assistant":
            continue

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ).strip()
            if text:
                return text
    return ""


def build_instruction(hits):
    listed = ", ".join(
        f'"{phrase}"' + (f" (x{count})" if count > 1 else "")
        for phrase, count in hits
    )
    return (
        "Your message leaned on stock phrasing: " + listed + ". Used this "
        "densely, these phrases recur across unrelated tasks and stop telling "
        "the reader anything about this one. Rewrite the message. For each, "
        "state the claim it was standing in for: what breaks, what changed, or "
        "what fails and when. Do not substitute a synonym. Do not shorten the "
        "message to avoid the problem — it is allowed to get longer."
    )


def main():
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    # Already blocked once this turn. Let it end rather than risk a loop.
    if event.get("stop_hook_active"):
        return 0

    text = event.get("last_assistant_message")
    if not isinstance(text, str) or not text.strip():
        text = transcript_fallback(event.get("transcript_path"))
    if not text.strip():
        return 0

    flag, hits, _stats = detect.assess(text)
    if not flag:
        return 0

    print(build_instruction(hits), file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
