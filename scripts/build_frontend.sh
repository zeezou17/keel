#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

if ! command -v npm >/dev/null 2>&1; then
  echo "error: npm was not found on PATH." >&2
  echo "Install Node.js 18+ and npm, then re-run this script." >&2
  echo "  conda install -c conda-forge nodejs" >&2
  echo "  https://nodejs.org/" >&2
  exit 1
fi

npm install
npm run build

echo "Frontend built to keel/static/"
