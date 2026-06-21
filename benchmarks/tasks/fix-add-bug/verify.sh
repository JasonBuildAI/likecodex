#!/usr/bin/env bash
# E2E verify: agent should fix the off-by-one bug in add().
set -euo pipefail
cd "$(dirname "$0")/workspace"
python -c "from add import add; assert add(1, 2) == 3"
