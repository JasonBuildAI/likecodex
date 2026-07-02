#!/bin/bash
set -euo pipefail
VERSION=$(cat VERSION)
echo "Releasing v$VERSION"
# 1. Update CHANGELOG.md
# 2. git tag v$VERSION
# 3. uv build && uv publish
# 4. cargo publish
echo "Done"
