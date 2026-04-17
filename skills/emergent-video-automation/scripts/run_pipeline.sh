#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <youtube_url>" >&2
  exit 2
fi

URL="$1"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 >/tmp/emergent-server.log 2>&1 &
PID=$!
trap 'kill $PID >/dev/null 2>&1 || true' EXIT
sleep 1

curl -sS -X POST "http://127.0.0.1:8080/process" \
  -H "Content-Type: application/json" \
  -d "{\"youtube_url\": \"${URL}\"}" | jq .
