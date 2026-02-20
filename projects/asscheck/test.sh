#!/usr/bin/env bash
# Project test runner for asscheck.
# Called by the factory's PostToolUse hook after any file edit in this project.
# Must exit 0 on pass, non-zero on failure.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Activate venv if present
if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi

# If no tests directory yet, pass silently (nothing to test)
if [[ ! -d "tests" ]]; then
  echo "[asscheck] no tests/ directory yet — skipping" >&2
  exit 0
fi

exec python -m pytest tests/ -v --tb=short
