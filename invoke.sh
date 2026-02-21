#!/usr/bin/env bash
# darkfactory — invoke.sh
#
# Fire the factory pipeline for a given spec file.
#
# Usage:
#   ./invoke.sh projects/<name>/specs/<spec>.md
#   ./invoke.sh projects/<name>/specs/<spec>.md --resume <session-id>
#
# The spec path determines which project is active. The project's CLAUDE.md
# is loaded and injected into the agent prompt automatically.
#
# Output: JSON run record in .claude/runs/<timestamp>-<project>-<slug>.json
# Resume a checkpointed run: ./invoke.sh <spec> --resume <session-id>

set -euo pipefail

FACTORY_ROOT="$(cd "$(dirname "$0")" && pwd)"
SPEC="${1:-}"
EXTRA_ARGS=("${@:2}")

if [[ -z "$SPEC" ]]; then
  echo "Usage: $0 projects/<name>/specs/<spec>.md [claude flags...]" >&2
  echo "" >&2
  echo "Projects:" >&2
  for dir in "$FACTORY_ROOT"/projects/*/; do
    [[ -d "$dir" ]] || continue
    name=$(basename "$dir")
    echo "  $name" >&2
  done
  exit 1
fi

SPEC_ABS="$FACTORY_ROOT/$SPEC"
if [[ ! -f "$SPEC_ABS" ]]; then
  echo "Spec not found: $SPEC" >&2
  exit 1
fi

# Infer project root from spec path (expects projects/<name>/...)
PROJECT_RELATIVE=$(echo "$SPEC" | grep -oP '^projects/[^/]+' || true)
if [[ -z "$PROJECT_RELATIVE" ]]; then
  echo "Spec must be under projects/<name>/ — got: $SPEC" >&2
  exit 1
fi

PROJECT_ROOT="$FACTORY_ROOT/$PROJECT_RELATIVE"
PROJECT_NAME=$(basename "$PROJECT_ROOT")
PROJECT_CLAUDE="$PROJECT_ROOT/CLAUDE.md"

PROJECT_CONTEXT=""
if [[ -f "$PROJECT_CLAUDE" ]]; then
  PROJECT_CONTEXT=$(cat "$PROJECT_CLAUDE")
fi

# Set up run record
RUN_DIR="$FACTORY_ROOT/.claude/runs"
mkdir -p "$RUN_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
SPEC_SLUG=$(basename "$SPEC" .md | tr ' /' '--')
RUN_FILE="$RUN_DIR/${TIMESTAMP}-${PROJECT_NAME}-${SPEC_SLUG}.json"

echo "[factory] project:  $PROJECT_NAME" >&2
echo "[factory] spec:     $SPEC" >&2
echo "[factory] run file: $RUN_FILE" >&2

PROMPT="You are an automated software factory agent.

## Active Project
Name:      $PROJECT_NAME
Root path: $PROJECT_ROOT

All file paths in the spec are relative to the project root above.
Use full absolute paths when creating or editing files.

## Project Conventions
$PROJECT_CONTEXT

## Task
Read the spec at: $SPEC_ABS

Workflow:
1. Explore $PROJECT_ROOT to understand existing code and patterns
2. Implement the spec — create all files under $PROJECT_ROOT
3. Tests auto-run via hooks after each edit; iterate until green
4. Commit directly to the current branch (do not create a new branch).
   Commit subject: '[automated] ${PROJECT_NAME}: <description>'

Work autonomously. Do not ask for clarification.
If the spec is ambiguous, take the simpler interpretation and note it in the commit."

claude -p "$PROMPT" \
  --allowedTools "Bash,Read,Edit,Write,Glob,Grep" \
  --output-format json \
  "${EXTRA_ARGS[@]}" \
  | tee "$RUN_FILE"

SESSION_ID=$(jq -r '.session_id // empty' "$RUN_FILE" 2>/dev/null || echo "")
if [[ -n "$SESSION_ID" ]]; then
  echo "" >&2
  echo "[factory] session: $SESSION_ID" >&2
  echo "[factory] resume:  $0 $SPEC --resume $SESSION_ID" >&2
fi
