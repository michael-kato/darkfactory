#!/usr/bin/env bash
# Project test runner for sdfs.
# Called by the factory's PostToolUse hook after any file edit in this project.
# Must exit 0 on pass, non-zero on failure.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

UNITY_PATH=""
if [[ -n "${UNITY_INSTALL:-}" ]]; then
  UNITY_PATH="$UNITY_INSTALL"
elif command -v Unity &>/dev/null; then
  UNITY_PATH="Unity"
elif [[ -d "/Applications/Unity/Hub/Editor" ]]; then
  UNITY_PATH="/Applications/Unity/Hub/Editor/$(ls -1 /Applications/Unity/Hub/Editor/ | head -1)/Contents/MacOS/Unity"
fi

if [[ -z "$UNITY_PATH" ]]; then
  echo "[sdfs] Unity not found, skipping build verification"
  echo "[sdfs] To enable tests, set UNITY_INSTALL environment variable or install Unity"
  exit 0
fi

echo "[sdfs] Running Unity batch mode build..."
"$UNITY_PATH" \
  -projectPath "$PROJECT_DIR/sdfs_uproj" \
  -quit \
  -batchmode \
  -nographics \
  -logFile /tmp/unity_build.log

if grep -qi "error:" /tmp/unity_build.log 2>/dev/null; then
  echo "[sdfs] Build failed:"
  grep -i "error:" /tmp/unity_build.log | head -10
  exit 1
fi

echo "[sdfs] Build successful"
exit 0
