#!/usr/bin/env bash
# ==============================================================================
# okonomi (お好み) - Local Preview Server
# ==============================================================================
set -e

PORT="${1:-8000}"

echo "🍱 Building encrypted apps..."
uv run python build.py

echo ""
echo "🚀 Serving encrypted docs at: http://localhost:${PORT}/"
echo "👉 Open test_page directly:   http://localhost:${PORT}/test_page/"
echo "🔑 Master password is in PASSWORD file"
echo "   (Press Ctrl+C to stop)"
echo ""

python3 -m http.server "$PORT" --directory docs
