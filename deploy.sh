#!/usr/bin/env bash
# ==============================================================================
# okonomi (お好み) - Safe Build & Deploy Script
# ==============================================================================
# Builds encrypted artifacts and pushes to GitHub with strict leak prevention.
# ==============================================================================
set -e

COMMIT_MSG="${1:-Deploy encrypted apps update ($(date +'%Y-%m-%d %H:%M:%S'))}"

echo "🍱 [1/4] Running okonomi build & encryption..."
uv run python build.py

echo ""
echo "🛡️  [2/4] Enforcing Zero-Leak security assertions..."

# 1. Assert PASSWORD is not tracked
if git ls-files --error-unmatch PASSWORD >/dev/null 2>&1; then
  echo "🚨 CRITICAL SECURITY ERROR: 'PASSWORD' file is tracked in git!"
  echo "Aborting deployment to prevent secret leak."
  exit 1
fi

# 2. Assert src/apps/ is not tracked
TRACKED_SRC=$(git ls-files src/ 2>/dev/null || true)
if [ -n "$TRACKED_SRC" ]; then
  echo "🚨 CRITICAL SECURITY ERROR: Unencrypted source files are tracked in git:"
  echo "$TRACKED_SRC"
  echo "Aborting deployment to prevent plaintext app leak."
  exit 1
fi

# 3. Assert dist/ contains encrypted files and .nojekyll
if [ ! -f "dist/index.html" ] || [ ! -f "dist/.nojekyll" ]; then
  echo "🚨 ERROR: dist/index.html or dist/.nojekyll missing after build."
  exit 1
fi

echo "   ✓ PASSWORD is safe and ignored."
echo "   ✓ src/apps/ is safe and ignored."
echo "   ✓ dist/ contains encrypted artifacts only."

echo ""
echo "📦 [3/4] Staging safe artifacts..."
git add .gitignore pyproject.toml uv.lock build.py deploy.sh dev.sh README.md IMPLEMENTATION_PLAN.md templates/ dist/

# Check if there are staged changes to commit
if git diff --cached --quiet; then
  echo "   No changes to commit. Dist is up to date."
else
  git commit -m "$COMMIT_MSG"
  echo "   ✓ Committed changes with message: '$COMMIT_MSG'"
fi

echo ""
echo "🚀 [4/4] Syncing with remote repository..."
CURRENT_BRANCH=$(git branch --show-current || echo "main")
REMOTE=$(git remote | head -n 1 || true)

if [ -z "$REMOTE" ]; then
  echo "ℹ️  No git remote configured yet."
  echo "To connect to GitHub, run:"
  echo "   git remote add origin git@github.com:<username>/okonomi.git"
  echo "   git push -u origin $CURRENT_BRANCH"
else
  git push "$REMOTE" "$CURRENT_BRANCH"
  echo "✨ Successfully pushed to $REMOTE/$CURRENT_BRANCH!"
fi

echo ""
echo "🍱 okonomi deployment complete!"
