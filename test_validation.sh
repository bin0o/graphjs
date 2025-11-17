#!/usr/bin/env sh
set -eu

# --- CONFIG ---
BASE="backtrace"
INPUT_DIR="$BASE/input"
OUTPUT_DIR="$BASE/output"
EXPECTED_DIR="$BASE/expected"
PREVIOUS_DIR="$BASE/previous_output_folder"

GRAPHJS="python3 graphjs.py"

# --- COLORS ---
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
RESET="\033[0m"

# --- FUNCTIONS ---

need_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    echo "This script needs 'jq'. Please install it (e.g., sudo apt install jq)." >&2
    exit 1
  fi
}

extract_sinks() {
  f="$1"
  [ -f "$f" ] || { echo ""; return; }
  jq -r '
    if type=="array" then
      map(select(has("sink_lineno")) | .sink_lineno)
      | unique | sort | join(",")
    elif type=="object" then
      if has("sink_lineno") then [ .sink_lineno ] | join(",") else "" end
    else ""
    end
  ' "$f" 2>/dev/null
}

summary_path_for_dir() {
  d="$1"
  if [ -f "$d/taint_summary_detection.json" ]; then
    echo "$d/taint_summary_detection.json"
  else
    echo "$d/taint_summary.json"
  fi
}

backup_output() {
  if [ -d "$OUTPUT_DIR" ]; then
    echo "${YELLOW}Backing up $OUTPUT_DIR → $PREVIOUS_DIR...${RESET}"
    rm -rf "$PREVIOUS_DIR"
    cp -a "$OUTPUT_DIR" "$PREVIOUS_DIR"
  else
    mkdir -p "$PREVIOUS_DIR"
  fi
  echo
}

# Run GraphJS on a single case directory with targeted retry for Neo4j timeout
run_case() {
  case_dir="$1" # e.g., backtrace/input/N/1
  out_dir="$(printf "%s\n" "$case_dir" | sed 's#/input/#/output/#')"
  mkdir -p "$out_dir"
  echo "Running $case_dir ..."

  max_attempts=3
  attempt=1
  while [ $attempt -le $max_attempts ]; do
    tmp="$(mktemp)"
    # Capture BOTH stdout and stderr
    $GRAPHJS -f "$case_dir" -o "$out_dir" >"$tmp" 2>&1
    status=$?

    if grep -Fq "[ERROR] Neo4j container was not successfully created (Timeout)." "$tmp"; then
      if [ $attempt -lt $max_attempts ]; then
        printf "  %bNeo4j timeout detected. Retrying (%d/%d)...%b\n" "$YELLOW" "$attempt" "$max_attempts" "$RESET"
        attempt=$((attempt+1))
        sleep 2
        rm -f "$tmp"
        continue
      else
        printf "  %bNeo4j timeout persisted after %d attempts.%b\n" "$RED" "$max_attempts" "$RESET"
        rm -f "$tmp"
        return 1
      fi
    fi

    # If no timeout string but non-zero exit, surface a concise error snippet
    if [ $status -ne 0 ]; then
      printf "  %bGraphJS exited with code %d. Output:%b\n" "$RED" "$status" "$RESET"
      head -n 5 "$tmp" | sed 's/^/    /'
      [ "$(wc -l < "$tmp")" -gt 5 ] && echo "    ..."
      rm -f "$tmp"
      return 1
    fi

    rm -f "$tmp"
    break
  done
}

compare_sinks() {
  dir_a="$1"
  dir_b="$2"
  file_a="$(summary_path_for_dir "$dir_a")"
  file_b="$(summary_path_for_dir "$dir_b")"
  sinks_a="$(extract_sinks "$file_a")"
  sinks_b="$(extract_sinks "$file_b")"
  if [ "$sinks_a" = "$sinks_b" ]; then
    echo "match"
  else
    echo "diff"
  fi
}

# --- MAIN ---

need_jq
backup_output

CASES="$(find "$INPUT_DIR" -mindepth 2 -maxdepth 2 -type d | sort)"

echo "========================================"
echo " Run against expected"
echo "========================================"

for case_dir in $CASES; do
  run_case "$case_dir" || true
  out_dir="$(printf "%s\n" "$case_dir" | sed 's#/input/#/output/#')"
  exp_dir="$(printf "%s\n" "$case_dir" | sed 's#/input/#/expected/#')"

  result="$(compare_sinks "$out_dir" "$exp_dir")"
  if [ "$result" = "match" ]; then
    printf "  %b✓ %s matches expected%b\n" "$GREEN" "$case_dir" "$RESET"
  else
    printf "  %b✗ %s differs from expected%b\n" "$RED" "$case_dir" "$RESET"
  fi
done

echo
echo "========================================"
echo " Run against previous output"
echo "========================================"

for case_dir in $CASES; do
  out_dir="$(printf "%s\n" "$case_dir" | sed 's#/input/#/output/#')"
  prev_dir="$(printf "%s\n" "$case_dir" | sed 's#/input/#/previous_output_folder/#')"

  result="$(compare_sinks "$out_dir" "$prev_dir")"
  # RED if it matches previous (no change), GREEN if different
  if [ "$result" = "match" ]; then
    printf "  %b✗ %s unchanged from previous%b\n" "$GREEN" "$case_dir" "$RESET"
  else
    printf "  %b✓ %s changed from previous%b\n" "$RED" "$case_dir" "$RESET"
  fi
done

echo
echo "${YELLOW}All tests completed.${RESET}"
