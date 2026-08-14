#!/usr/bin/env bash
# Long-session decay test.
#
# The single-shot eval (run.sh) found no difference between a plain-English
# prompt and this plugin. That is the predicted result: at turn 1 a prompt
# instruction and a system-prompt instruction are both fresh, so the arms should
# look identical.
#
# The claim is about what happens later. A prompt instruction is one user
# message near the top of the conversation; as turns accumulate it gets buried,
# and the model's own prior output becomes the in-context example for the next
# turn. An output style sits in the system prompt and re-triggers adherence
# reminders mid-conversation. If that mechanism is real, the arms diverge with
# turn number:
#
#              turn 1      turn N
#   plain      good        degraded
#   plugin     good        flat
#
# So the measurement is a slope, not a difference of means. This drives one
# genuine multi-turn session per arm through the same task sequence, saving
# every turn separately so score.py can plot metric against turn index.
#
#   ./decay.sh                                   # bundled fixture (small)
#   SUBSTRATE=~/dev/bigrepo TURNS=turns-repo.txt ./decay.sh
#
# Turn prompts come from a file, one per line, blank lines ignored.

set -uo pipefail

cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
OUT="$(pwd)/out-decay"

MODEL="${MODEL:-claude-opus-5}"
EFFORT="${EFFORT:-xhigh}"
SUBSTRATE="${SUBSTRATE:-}"
TURNS_FILE="${TURNS:-turns-repo.txt}"
TOOLS="Read,Grep,Glob,Bash"
ARMS=(${ARMS_OVERRIDE:-none plain plugin})

PLAIN_PREFIX='Write in plain technical English. Do not reference things I have not seen or would not know.

'

[ -f "$TURNS_FILE" ] || { echo "no turns file: $TURNS_FILE" >&2; exit 1; }
mkdir -p "$OUT"

WORKDIR="${SUBSTRATE:-$(pwd)/fixture}"

echo "model:     $MODEL (effort $EFFORT)"
echo "workdir:   $WORKDIR"
echo "turns:     $(grep -cve '^\s*$' "$TURNS_FILE") from $TURNS_FILE"
echo "arms:      ${ARMS[*]}"
echo

run_arm() {
  local arm="$1"
  local session=""
  local turn=0

  local extra=()
  [ "$arm" = "plugin" ] && extra=(--plugin-dir "$ROOT")

  while IFS= read -r line; do
    [ -z "${line// }" ] && continue
    turn=$(( turn + 1 ))

    local prompt="$line"
    # Only the first turn carries the instruction. That is the point: a prompt
    # instruction is delivered once, and the question is whether it holds.
    if [ "$arm" = "plain" ] && [ "$turn" = "1" ]; then
      prompt="${PLAIN_PREFIX}${line}"
    fi

    local resume=()
    [ -n "$session" ] && resume=(--resume "$session")

    local raw="$OUT/${arm}__turn$(printf '%02d' "$turn").json"
    local md="$OUT/${arm}__turn$(printf '%02d' "$turn").md"

    if ! ( cd "$WORKDIR" && claude -p "$prompt" \
             --model "$MODEL" \
             --effort "$EFFORT" \
             --permission-mode acceptEdits \
             --allowedTools "$TOOLS" \
             ${extra[@]+"${extra[@]}"} \
             ${resume[@]+"${resume[@]}"} \
             --output-format json ) > "$raw" 2>"$OUT/${arm}__turn$(printf '%02d' "$turn").err" < /dev/null; then
      echo "  $arm turn $turn: FAILED"
      return 1
    fi

    session="$(python3 - "$raw" "$md" <<'PY'
import json, sys
raw, md = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(raw))
except Exception:
    d = {}
open(md, "w").write(d.get("result") or "")
print(d.get("session_id", ""))
PY
)"
    local words; words=$(wc -w < "$md" | tr -d ' ')
    echo "  $arm turn $turn: ${words}w  session=${session:0:8}"

    if [ -z "$session" ]; then
      echo "  $arm: no session_id returned, cannot continue the session" >&2
      return 1
    fi
  done < "$TURNS_FILE"
}

# Turns within an arm must be sequential -- each resumes the previous session.
# Arms are independent, so they run concurrently.
for arm in "${ARMS[@]}"; do
  ( run_arm "$arm" || echo "  (arm $arm incomplete)" ) &
done
wait

echo "score: python3 score_decay.py"
