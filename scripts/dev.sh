#!/usr/bin/env bash
# LikeCodex development launcher for Unix.

set -euo pipefail

SKIP_WEB=false
SKIP_SERVER=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-web) SKIP_WEB=true; shift ;;
    --skip-server) SKIP_SERVER=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

cleanup() {
  echo "Stopping LikeCodex dev environment..."
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Building Rust workspace..."
cargo build

if [[ "$SKIP_SERVER" == "false" ]]; then
  echo "==> Starting Python engine bridge on :9090..."
  uv run python -m likecodex_engine.server &
  echo "==> Starting Rust API server on :8080..."
  cargo run -p likecodex-server &
fi

if [[ "$SKIP_WEB" == "false" ]]; then
  echo "==> Starting Web UI on :3000..."
  (cd web && npm run dev) &
fi

echo "==> LikeCodex dev environment started."
echo "    Engine :9090 | API :8080 | Web :3000"
wait
