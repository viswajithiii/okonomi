#!/usr/bin/env bash
# ==============================================================================
# okonomi (お好み) - Local Preview Server
# ==============================================================================
set -e

PORT="${1:-8000}"

echo "🍱 Building encrypted portal..."
uv run python build.py

echo ""
echo "🚀 Serving encrypted dist at: http://localhost:${PORT}/"
echo "🔑 Master password is in PASSWORD file"
echo "   (Press Ctrl+C to stop)"
echo ""

python3 -m http.server "$PORT" --directory dist
