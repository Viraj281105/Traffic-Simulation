#!/usr/bin/env sh
# Worker-kill experiment: run a k6 load while the backend is killed and restarted, then
# evaluate the SLOs. Dry run unless EXECUTE=1. WRITTEN, not run.
#   EXECUTE=1 BASE_URL=http://127.0.0.1:8000 AUTH_TOKEN=... sh deploy/chaos/worker-kill.sh
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
EXEC=""
[ "${EXECUTE:-0}" = "1" ] && EXEC="--execute"
if [ -z "$EXEC" ]; then
  echo "DRY RUN: set EXECUTE=1 to run. Would: start k6 smoke in background, then kill-backend."
  python "$HERE/chaos.py" kill-backend
  exit 0
fi
k6 run "$HERE/../k6/load.js" &
K6_PID=$!
sleep 30
python "$HERE/chaos.py" kill-backend --execute --down-seconds 20
wait "$K6_PID" || echo "k6 thresholds failed during the kill window (expected to show the impact)"
