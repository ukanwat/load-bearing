#!/usr/bin/env bash
# Three-arm A/B/C sweep, run in parallel.
#
#   none    unmodified Claude Code
#   plain   "Write in plain technical English." appended to the prompt
#   plugin  load-bearing loaded via --plugin-dir
#
# `plain` is the arm that matters. Beating an unmodified baseline proves little,
# because a single sentence in the prompt already helps. The question this eval
# exists to answer is whether a plugin beats that sentence.
#
#   ./run.sh                                  # bundled fixture, 2 reps
#   REPS=3 ./run.sh                           # more reps, less variance
#   SUBSTRATE=~/dev/myrepo TASKS_DIR=tasks-repo ./run.sh
#   MODEL=claude-opus-4-8 ./run.sh
#
# Repetitions are not optional. Stock-phrase counts land in the single digits
# per response, so one run per arm cannot separate an effect from variance.

set -uo pipefail

cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
OUT="$(pwd)/out"

MODEL="${MODEL:-claude-opus-5}"
EFFORT="${EFFORT:-xhigh}"
REPS="${REPS:-2}"
MAXJOBS="${MAXJOBS:-5}"
TASKS_DIR="${TASKS_DIR:-tasks}"
SUBSTRATE="${SUBSTRATE:-}"
TOOLS="Read,Grep,Glob,Bash"
ARMS=(none plain plugin)

PLAIN_SUFFIX=$'\n\nWrite in plain technical English.'

TASKS=("$@")
if [ ${#TASKS[@]} -eq 0 ]; then
  TASKS=("$TASKS_DIR"/*.md)
fi

mkdir -p "$OUT"

# With no SUBSTRATE, each run gets a private copy of the bundled fixture so
# concurrent runs cannot interfere. With one, runs share it read-only.
prepare_dir() {
  local tag="$1"
  if [ -n "$SUBSTRATE" ]; then
    echo "$SUBSTRATE"
    return
  fi
  local dir="arms/$tag"
  rm -rf "$dir"; mkdir -p "$dir"
  cp -R fixture/ "$dir/"
  rm -rf "$dir/.claude"
  echo "$dir"
}

run_one() {
  local task="$1" arm="$2" rep="$3"
  local name; name="$(basename "$task" .md)"
  local tag="${name}__rep${rep}__${arm}"
  local outfile="$OUT/${tag}.md"
  local errfile="$OUT/${tag}.err"

  local prompt; prompt="$(cat "$task")"
  [ "$arm" = "plain" ] && prompt="${prompt}${PLAIN_SUFFIX}"

  local extra=()
  [ "$arm" = "plugin" ] && extra=(--plugin-dir "$ROOT")

  local dir; dir="$(prepare_dir "$tag")"
  local start; start=$(date +%s)

  # bash 3.2 (macOS) treats "${arr[@]}" on an empty array as unbound under -u.
  if ( cd "$dir" && claude -p "$prompt" \
         --model "$MODEL" \
         --effort "$EFFORT" \
         --permission-mode acceptEdits \
         --allowedTools "$TOOLS" \
         ${extra[@]+"${extra[@]}"} \
         --output-format text ) > "$outfile" 2> "$errfile" < /dev/null; then
    local elapsed=$(( $(date +%s) - start ))
    local words; words=$(wc -w < "$outfile" | tr -d ' ')
    if [ "$words" -lt 20 ]; then
      echo "   EMPTY  $tag (${elapsed}s)"
    else
      echo "   ok     $tag  ${elapsed}s  ${words}w"
    fi
  else
    echo "   FAIL   $tag — $(tail -1 "$errfile" | cut -c1-90)"
  fi
  [ -z "$SUBSTRATE" ] && rm -rf "arms/$tag"
  return 0
}

echo "model:     $MODEL (effort $EFFORT)"
echo "substrate: ${SUBSTRATE:-bundled fixture}"
echo "tasks:     ${#TASKS[@]} from $TASKS_DIR"
echo "arms:      ${ARMS[*]}"
echo "reps:      $REPS"
echo "total:     $(( ${#TASKS[@]} * ${#ARMS[@]} * REPS )) runs, $MAXJOBS concurrent"
echo

for task in "${TASKS[@]}"; do
  for rep in $(seq 0 $(( REPS - 1 )) ); do
    for arm in "${ARMS[@]}"; do
      while [ "$(jobs -rp | wc -l)" -ge "$MAXJOBS" ]; do sleep 2; done
      run_one "$task" "$arm" "$rep" &
    done
  done
done

wait
echo
echo "score:  python3 score.py"
echo "judge:  python3 judge.py --reps 2"
