#!/usr/bin/env bash
# Stop hook — fires when Claude tries to finish responding.
# Blocks completion if the last test run was red.
# Green, no-tests, and missing status all allow stopping.

set -euo pipefail

FACTORY_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATUS_FILE="$FACTORY_ROOT/.claude/test-status"

if [[ ! -f "$STATUS_FILE" ]]; then
  exit 0
fi

STATUS=$(cat "$STATUS_FILE")

if [[ "$STATUS" == "red" ]]; then
  echo '{"decision":"block","reason":"Tests are failing. Fix all test failures before finishing."}'
  exit 2
fi

exit 0