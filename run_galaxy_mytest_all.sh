#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-log/mytest}"
MODEL="${MODEL:-google/gemini-2.5-pro}"
FACTOR_CONCURRENCY="${FACTOR_CONCURRENCY:-5}"
TASK_CONCURRENCY="${TASK_CONCURRENCY:-3}"
REASONING_EFFORT="${REASONING_EFFORT:-low}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found in PATH." >&2
  exit 1
fi

cd "$ROOT_DIR"

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Target directory not found: $TARGET_DIR" >&2
  exit 1
fi

shopt -s nullglob
dirs=("$TARGET_DIR"/*/)
shopt -u nullglob

if [[ ${#dirs[@]} -eq 0 ]]; then
  echo "No subdirectories found under $TARGET_DIR" >&2
  exit 1
fi

for dir in "${dirs[@]}"; do
  dir="${dir%/}"
  echo "Running Galaxy analysis for: $dir"
  uv run galaxy_assistant/galaxy_main.py \
    -b \
    -f "$dir" \
    -m "$MODEL" \
    -fc "$FACTOR_CONCURRENCY" \
    -tc "$TASK_CONCURRENCY" \
    --reasoning-effort "$REASONING_EFFORT"
done
