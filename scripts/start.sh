#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip -q install --upgrade pip >/dev/null
pip -q install fastapi uvicorn[standard] sqlmodel python-dotenv requests cryptography reportlab pandas >/dev/null
python3 -m uvicorn main:app --host 0.0.0.0 --port 8010
