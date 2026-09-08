#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
