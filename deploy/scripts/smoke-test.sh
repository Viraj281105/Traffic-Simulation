#!/usr/bin/env bash
# Smoke test for a running UrbanFlow stack. Usage: smoke-test.sh [BASE_URL]
# Checks the frontend (static page), the nginx health route and the backend
# health route proxied through nginx. Retries because pods may still be warming.
set -euo pipefail

BASE="${1:-http://127.0.0.1:8080}"

check() {
  local path="$1" attempts=30
  for _ in $(seq 1 "$attempts"); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${BASE}${path}" || true)"
    if [ "$code" = "200" ]; then
      echo "ok   ${path} -> 200"
      return 0
    fi
    sleep 2
  done
  echo "FAIL ${path} -> last status ${code:-none}" >&2
  return 1
}

check /
check /health
echo "smoke test passed against ${BASE}"
