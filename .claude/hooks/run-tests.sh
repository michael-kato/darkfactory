#!/usr/bin/env bash
# PostToolUse hook — fires after Edit or Write.
# Detects which project the edited file belongs to, runs that project's test.sh,
# and writes pass/fail status to .claude/test-status for the Stop gate.

set -euo pipefail

FACTORY_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATUS_FILE="$FACTORY_ROOT/.claude/test-status"

# Read tool input from stdin
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || echo "")

if [[ -z "$FILE_PATH" ]]; then
  echo "no-tests" > "$STATUS_FILE"
  exit 0
fi

# Find which project this file belongs to
PROJECT_DIR=""
if [[ "$FILE_PATH" == "$FACTORY_ROOT/projects/"* ]]; then
  RELATIVE="${FILE_PATH#$FACTORY_ROOT/}"
  PROJECT_NAME=$(echo "$RELATIVE" | cut -d/ -f2)
  PROJECT_DIR="$FACTORY_ROOT/projects/$PROJECT_NAME"
fi

if [[ -z "$PROJECT_DIR" || ! -d "$PROJECT_DIR" ]]; then
  # Edit outside a project directory (factory infra, specs, etc.) — skip tests
  echo "no-tests" > "$STATUS_FILE"
  exit 0
fi

TEST_SCRIPT="$PROJECT_DIR/test.sh"
if [[ ! -f "$TEST_SCRIPT" ]]; then
  echo "no-tests" > "$STATUS_FILE"
  echo "[hook] no test.sh in $(basename "$PROJECT_DIR") — skipping" >&2
  exit 0
fi

if bash "$TEST_SCRIPT" 2>&1; then
  echo "green" > "$STATUS_FILE"
  echo "[hook] tests passed ($(basename "$PROJECT_DIR"))" >&2
else
  echo "red" > "$STATUS_FILE"
  echo "[hook] tests FAILED ($(basename "$PROJECT_DIR")) — Claude will iterate before finishing" >&2
fi

# Always exit 0: status is reported, not enforced here.
# Blocking happens in require-green.sh at the Stop event.
exit 0