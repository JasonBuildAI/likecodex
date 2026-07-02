#!/usr/bin/env bash
# ============================================================================
# LikeCodex PyPI Publishing Script
# ============================================================================
# Usage:
#   ./scripts/publish.sh              # Build and publish (dry-run first)
#   ./scripts/publish.sh --release     # Actually publish to PyPI
#   ./scripts/publish.sh --test        # Publish to TestPyPI
#   ./scripts/publish.sh --build-only  # Only build wheels, no upload
#
# Prerequisites:
#   - Python 3.11+ with `uv` installed
#   - PyPI API token in ~/.pypirc or TWINE_PASSWORD env
# ============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔨 LikeCodex Build & Publish Script${NC}"
echo "Working directory: $PROJECT_ROOT"
echo ""

# ── Validate prerequisites ──
if ! command -v uv &>/dev/null; then
    echo -e "${RED}Error: 'uv' is not installed. Install it from https://docs.astral.sh/uv/${NC}"
    exit 1
fi

# ── Parse arguments ──
DO_RELEASE=false
DO_TEST=false
DO_BUILD_ONLY=false

for arg in "$@"; do
    case "$arg" in
    --release) DO_RELEASE=true ;;
    --test) DO_TEST=true ;;
    --build-only) DO_BUILD_ONLY=true ;;
    *) echo -e "${RED}Unknown option: $arg${NC}" && exit 1 ;;
    esac
done

# ── Clean previous builds ──
echo -e "${YELLOW}🧹 Cleaning previous builds...${NC}"
rm -rf dist/ build/ *.egg-info
echo "Done."

# ── Build wheel and source distribution ──
echo -e "${YELLOW}📦 Building wheel and sdist...${NC}"
uv build --all-packages
echo -e "${GREEN}✅ Build complete.${NC}"
echo ""

ls -lh dist/

# ── Exit if build-only ──
if [ "$DO_BUILD_ONLY" = true ]; then
    echo -e "${GREEN}Build-only mode. Artifacts in dist/.${NC}"
    exit 0
fi

# ── Dry-run check (always unless --release) ──
if [ "$DO_RELEASE" = false ] && [ "$DO_TEST" = false ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Dry-run mode. Use --release to actually publish.${NC}"
    echo -e "${YELLOW}   Build artifacts are in dist/ ready for inspection.${NC}"
    echo ""
    echo "To publish to TestPyPI:  ./scripts/publish.sh --test"
    echo "To publish to PyPI:      ./scripts/publish.sh --release"
    exit 0
fi

# ── Publish to TestPyPI ──
if [ "$DO_TEST" = true ]; then
    echo -e "${YELLOW}🧪 Publishing to TestPyPI...${NC}"
    uv publish \
        --publish-url https://test.pypi.org/legacy/ \
        --trusted-publishing always \
        dist/*
    echo -e "${GREEN}✅ Published to TestPyPI!${NC}"
    echo "  https://test.pypi.org/project/likecodex/"
    exit 0
fi

# ── Publish to PyPI ──
if [ "$DO_RELEASE" = true ]; then
    echo -e "${YELLOW}🚀 Publishing to PyPI...${NC}"
    uv publish \
        --trusted-publishing always \
        dist/*
    echo -e "${GREEN}✅ Published to PyPI!${NC}"
    echo "  https://pypi.org/project/likecodex/"

    # Tag the release if not already tagged
    VERSION=$(grep '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
    if git rev-parse "v$VERSION" >/dev/null 2>&1; then
        echo -e "${YELLOW}Tag v$VERSION already exists. Skipping.${NC}"
    else
        echo -e "${YELLOW}Creating git tag v$VERSION...${NC}"
        git tag "v$VERSION"
        echo -e "${GREEN}Tag v$VERSION created. Push with: git push origin v$VERSION${NC}"
    fi
fi
