#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate it
source .venv/bin/activate

# Install dependencies if needed
pip install -q -r requirements.txt

echo ""
echo "  logdiff running at http://localhost:8000"
echo "  Press Ctrl+C to stop"
echo ""

uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
