#!/usr/bin/env bash
pkill -f 'uvicorn main:app' 2>/dev/null || true
pkill -f cloudflared 2>/dev/null || true
echo "Stopped uvicorn and cloudflared (if running)."
