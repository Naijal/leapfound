#!/usr/bin/env bash
set -e
cloudflared tunnel --url http://127.0.0.1:8010 --edge-ip-version auto
