#!/usr/bin/env bash
set -euo pipefail

REPO="${LIKECODEX_INSTALL_REPO:-https://github.com/JasonBuildAI/likecodex.git}"
INSTALL_DIR="${LIKECODEX_INSTALL_DIR:-$HOME/.likecodex/install}"

echo "==> LikeCodex installer"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -fsSL https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "Rust/cargo is required — install from https://rustup.rs" >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR"
if [ ! -d "$INSTALL_DIR/.git" ]; then
  git clone "$REPO" "$INSTALL_DIR"
else
  git -C "$INSTALL_DIR" pull --ff-only
fi

cd "$INSTALL_DIR"
uv sync --all-packages
cargo install --path crates/likecodex-cli --force

mkdir -p "$HOME/.likecodex"
if [ ! -f "$HOME/.likecodex/config.toml" ]; then
  cat >"$HOME/.likecodex/config.toml" <<'EOF'
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"

[approval]
mode = "auto"

[agent]
max_steps = 50
planner_model = "deepseek-v4-pro"
executor_model = "deepseek-v4-flash"
compact_ratio = 0.8
enable_planner = false
EOF
fi

echo "==> Done. Run: likecodex doctor && likecodex code"
