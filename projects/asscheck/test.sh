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

# Allow override via env var (useful for CI or alternate Blender installs)
BLENDER="${BLENDER_BIN:-/opt/blender-5.0.1-linux-x64/blender}"

# -- Pure Python tests (schema, intake) ------------------------------------
# Fast, no Blender required. Always run these first for quick feedback.
echo "[asscheck] running pure-python tests..."
python -m pytest tests/schema.py tests/intake.py -v --tb=short

# -- Blender integration tests --------------------------------------------
# Runs inside a single Blender process. Tests skip gracefully if assets/ missing.
if [[ ! -f "$BLENDER" ]]; then
  echo "[asscheck] WARNING: Blender not found at $BLENDER — skipping integration tests" >&2
  echo "[asscheck] Set BLENDER_BIN to the blender binary path to enable them." >&2
  sleep 10
  exit 0
fi

echo "[asscheck] running blender integration tests..."
exec "$BLENDER" --background --python tests/blender.py

sleep 10
