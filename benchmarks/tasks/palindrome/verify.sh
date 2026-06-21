#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/workspace"
python -c "from palindrome import is_palindrome; assert is_palindrome('racecar')"
