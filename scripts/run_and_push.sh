#!/usr/bin/env bash
# ADAS Weekly — generate report locally and push to GitHub
# Run manually: bash scripts/run_and_push.sh
# Or install the launchd plist for Friday automation.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# Load .env if present
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

# Require API key
if [[ -z "${LLM_API_KEY:-}" ]]; then
  echo "ERROR: LLM_API_KEY is not set. Copy .env.example to .env and fill it in."
  exit 1
fi

echo "=== ADAS Weekly — $(date '+%Y-%m-%d %H:%M') ==="

# Run pipeline
.venv/bin/python main.py

# Stage generated output
git add output/

if git diff --cached --quiet; then
  echo "No changes in output/ — nothing to push."
  exit 0
fi

WEEK=$(date '+%Y-W%V')
git commit -m "report: ${WEEK} weekly ADAS report"
git push

echo "=== Done. Report pushed. ==="
