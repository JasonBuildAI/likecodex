#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/workspace"
python -c "from fizzbuzz import fizzbuzz; assert fizzbuzz(15) == 'FizzBuzz'"
