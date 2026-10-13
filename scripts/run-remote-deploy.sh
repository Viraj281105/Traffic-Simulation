#!/usr/bin/env bash
# ==============================================================================
# UrbanFlow / Traffic-Simulation: GitHub-runner side of the EC2 deployment
# ==============================================================================
# Runs on the GitHub Actions runner (called from .github/workflows/deploy.yml).
#
# Why this exists: the Docker image build on EC2 can take several minutes and,
# on a 1 GB instance, can starve sshd. When the deployment was a single
# foreground `ssh host deploy-ec2.sh`, one dropped connection ("client_loop:
# send disconnect: Broken pipe", exit 255) killed the deployment mid-flight and
# the runner could not tell whether the build had failed or only the transport.
#
# Instead this script:
#   1. Starts scripts/deploy-ec2.sh on EC2 detached from the SSH session
#      (setsid + nohup), logging to a state directory and recording its exit
#      status in a file only after the script has actually finished.
#   2. Polls with short, independent SSH calls (keepalives on, hard timeouts,
#      tolerant of transient failures), streaming new log bytes as they appear.
#   3. Exits 0 ONLY when the remote status file says the deployment script
#      exited 0. A dropped connection, a vanished process, or a poll timeout is
#      always reported as a failure, never as success.
#   4. On any failure, collects best-effort diagnostics from EC2 (memory, disk,
#      kernel OOM events, containers, log tail) so SSH/resource problems can be
#      told apart from application/build problems.
#
# Required environment: EC2_USER, EC2_HOST, TARGET_COMMIT
# Optional environment: EC2_PORT (22), DEPLOY_PATH (~/Traffic-Simulation),
#   SSH_KEY_FILE (~/.ssh/ec2_deploy_key), SSH_BIN (ssh),
#   REMOTE_SCRIPT_PATH (/tmp/deploy-ec2.sh), POLL_INTERVAL (15),
#   MAX_CONSECUTIVE_SSH_FAILURES (40), DEPLOY_TIMEOUT_SECONDS (2400),
#   GITHUB_RUN_ID / GITHUB_RUN_ATTEMPT (state-directory key)
# ==============================================================================

set -Eeuo pipefail

: "${EC2_USER:?EC2_USER is required}"
: "${EC2_HOST:?EC2_HOST is required}"
: "${TARGET_COMMIT:?TARGET_COMMIT is required}"

EC2_PORT="${EC2_PORT:-22}"
DEPLOY_PATH="${DEPLOY_PATH:-~/Traffic-Simulation}"
SSH_KEY_FILE="${SSH_KEY_FILE:-$HOME/.ssh/ec2_deploy_key}"
SSH_BIN="${SSH_BIN:-ssh}"
REMOTE_SCRIPT_PATH="${REMOTE_SCRIPT_PATH:-/tmp/deploy-ec2.sh}"
POLL_INTERVAL="${POLL_INTERVAL:-15}"
MAX_CONSECUTIVE_SSH_FAILURES="${MAX_CONSECUTIVE_SSH_FAILURES:-40}"
DEPLOY_TIMEOUT_SECONDS="${DEPLOY_TIMEOUT_SECONDS:-2400}"
RUN_KEY="${GITHUB_RUN_ID:-manual}-${GITHUB_RUN_ATTEMPT:-1}"

# Both values end up in a remote command line; refuse anything unexpected.
if [[ ! "$TARGET_COMMIT" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
    echo "::error::TARGET_COMMIT must be a 7-40 character hex commit SHA." >&2
    exit 1
fi
if [[ ! "$RUN_KEY" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "::error::Invalid run key '$RUN_KEY'." >&2
    exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# remote <timeout-seconds> <remote command...>  (stdin is passed to the remote)
# Keepalives make a dead peer fail the call within ~60s instead of hanging;
# `timeout` bounds the call regardless of what ssh itself does.
remote() {
    local limit="$1"
    shift
    timeout "$limit" "$SSH_BIN" \
        -i "$SSH_KEY_FILE" \
        -p "$EC2_PORT" \
        -o BatchMode=yes \
        -o ConnectTimeout=15 \
        -o ServerAliveInterval=15 \
        -o ServerAliveCountMax=4 \
        "${EC2_USER}@${EC2_HOST}" \
        "$@"
}

# Quote positional arguments for the remote shell.
quote_args() {
    local out="" a
    for a in "$@"; do
        out+="$(printf '%q' "$a") "
    done
    printf '%s' "$out"
}

# ------------------------------------------------------------------------------
# Remote scripts (sent over stdin to `bash -s -- <args>`; nothing is expanded
# locally because the heredoc delimiters are quoted).
# ------------------------------------------------------------------------------

IFS= read -r -d '' LAUNCH_SCRIPT <<'REMOTE_EOF' || true
set -eu
run_key=$1; commit=$2; repo=$3; src=$4
root="$HOME/.urbanflow-deploy"
dir="$root/$run_key"
mkdir -p "$dir"
chmod 700 "$root" "$dir"
# Housekeeping: drop state of deployments older than two weeks.
find "$root" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} + 2>/dev/null || true

# Idempotent: a retried launch must never start a second deployment.
if [ -e "$dir/pid" ] || [ -e "$dir/status" ]; then
    echo "already-launched"
    exit 0
fi
if [ ! -f "$src" ]; then
    echo "deployment script $src is missing on the instance" >&2
    exit 2
fi
cp "$src" "$dir/deploy-ec2.sh"
: > "$dir/deploy.log"

launcher=""
if command -v setsid >/dev/null 2>&1; then launcher="setsid"; fi

# Detached from the SSH session: own session, no controlling terminal, no stdio
# tied to the channel. The status file is written (atomically) only after the
# deployment script has exited, so its presence means "finished" and its content
# is the real exit code.
nohup $launcher bash -c '
  echo $$ > "$1/pid"
  rc=0
  bash "$1/deploy-ec2.sh" --commit "$2" --repo-dir "$3" >> "$1/deploy.log" 2>&1 || rc=$?
  echo "$rc" > "$1/status.tmp"
  mv "$1/status.tmp" "$1/status"
' _ "$dir" "$commit" "$repo" </dev/null >/dev/null 2>&1 &

i=0
while [ ! -s "$dir/pid" ] && [ "$i" -lt 100 ]; do
    sleep 0.1
    i=$((i + 1))
done
if [ ! -s "$dir/pid" ]; then
    echo "detached deployment process did not start" >&2
    exit 3
fi
echo "launched"
REMOTE_EOF

IFS= read -r -d '' POLL_SCRIPT <<'REMOTE_EOF' || true
dir="$HOME/.urbanflow-deploy/$1"; off=$2
state() {
    if [ -f "$dir/status" ]; then echo "DONE $(cat "$dir/status")"; return; fi
    if [ -s "$dir/pid" ] && kill -0 "$(cat "$dir/pid")" 2>/dev/null; then echo RUNNING; return; fi
    # Re-check: the process may have finished between the two tests above.
    if [ -f "$dir/status" ]; then echo "DONE $(cat "$dir/status")"; return; fi
    if [ -s "$dir/pid" ]; then echo DEAD; else echo NOPID; fi
}
# State first, then the log: when the state is DONE the log read below is complete.
state
tail -c +"$((off + 1))" "$dir/deploy.log" 2>/dev/null || true
REMOTE_EOF

IFS= read -r -d '' DIAG_SCRIPT <<'REMOTE_EOF' || true
dir="$HOME/.urbanflow-deploy/$1"
echo "--- uptime / load ---";            uptime 2>&1
echo "--- memory (MB) ---";              free -m 2>&1
echo "--- disk ---";                     df -h / 2>&1
echo "--- kernel OOM-killer events (last 20) ---"
( dmesg 2>/dev/null || sudo -n dmesg 2>/dev/null ) | grep -iE 'out of memory|oom-kill|killed process' | tail -n 20
echo "--- docker disk usage ---";        { docker system df 2>/dev/null || sudo -n docker system df 2>/dev/null; }
echo "--- containers ---";               { docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' 2>/dev/null || sudo -n docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' 2>/dev/null; }
echo "--- deployment state files ---";   ls -l "$dir" 2>&1
echo "--- deployment log (last 60 lines) ---"; tail -n 60 "$dir/deploy.log" 2>&1
exit 0
REMOTE_EOF

# ------------------------------------------------------------------------------

collect_diagnostics() {
    echo "::group::Remote diagnostics from EC2 (best effort)"
    if ! remote 90 "bash -s -- $(quote_args "$RUN_KEY")" <<<"$DIAG_SCRIPT"; then
        echo "Diagnostics unavailable: the instance could not be reached over SSH."
        echo "That itself is evidence of an SSH/network/instance problem rather than a build error."
    fi
    echo "::endgroup::"
}

fail() {
    echo "::error::$*"
    collect_diagnostics
    echo "The detached deployment, if still running, is NOT stopped by this failure."
    echo "Its state lives on EC2 in ~/.urbanflow-deploy/${RUN_KEY}/ (deploy.log, status)."
    exit 1
}

# --- 1. Launch (detached) ----------------------------------------------------
echo "Launching detached deployment on ${EC2_HOST} (commit ${TARGET_COMMIT}, run ${RUN_KEY})..."
LAUNCH_RESULT=""
for attempt in 1 2 3; do
    if LAUNCH_RESULT="$(remote 60 "bash -s -- $(quote_args "$RUN_KEY" "$TARGET_COMMIT" "$DEPLOY_PATH" "$REMOTE_SCRIPT_PATH")" <<<"$LAUNCH_SCRIPT")"; then
        break
    fi
    LAUNCH_RESULT=""
    echo "::warning::Launch attempt ${attempt}/3 failed; retrying (the launcher is idempotent)."
    sleep 5
done
if [[ "$LAUNCH_RESULT" != "launched" && "$LAUNCH_RESULT" != "already-launched" ]]; then
    fail "Could not start or confirm the detached deployment on EC2 (SSH or launcher failure)."
fi
echo "Deployment process: ${LAUNCH_RESULT}. Streaming its log..."

# --- 2. Poll until the remote script reports a real exit status ---------------
OFFSET=0
SSH_FAILURES=0
NOPID_POLLS=0
OUT="$TMP_DIR/poll.out"
CHUNK="$TMP_DIR/poll.chunk"

while true; do
    if (( SECONDS > DEPLOY_TIMEOUT_SECONDS )); then
        fail "Deployment did not finish within ${DEPLOY_TIMEOUT_SECONDS}s. It was NOT confirmed successful."
    fi

    POLL_RC=0
    remote 90 "bash -s -- $(quote_args "$RUN_KEY" "$OFFSET")" <<<"$POLL_SCRIPT" >"$OUT" 2>"$TMP_DIR/poll.err" || POLL_RC=$?

    STATE="$(head -n 1 "$OUT" 2>/dev/null || true)"
    if [[ "$STATE" =~ ^(DONE\ [0-9]+|RUNNING|DEAD|NOPID)$ ]]; then
        HEADER_BYTES=$(( ${#STATE} + 1 ))
        tail -c +$(( HEADER_BYTES + 1 )) "$OUT" >"$CHUNK"
        CHUNK_BYTES="$(wc -c <"$CHUNK")"
        if (( CHUNK_BYTES > 0 )); then
            cat "$CHUNK"
            OFFSET=$(( OFFSET + CHUNK_BYTES ))
        fi
    else
        STATE=""
    fi

    if (( POLL_RC != 0 )) || [[ -z "$STATE" ]]; then
        # Partial output (if any) was kept above; the state is untrusted on error.
        SSH_FAILURES=$(( SSH_FAILURES + 1 ))
        echo "::warning::Status poll failed (exit ${POLL_RC}, ${SSH_FAILURES}/${MAX_CONSECUTIVE_SSH_FAILURES} consecutive). The deployment keeps running on EC2."
        sed -e 's/^/    ssh: /' "$TMP_DIR/poll.err" | head -n 3 || true
        if (( SSH_FAILURES >= MAX_CONSECUTIVE_SSH_FAILURES )); then
            fail "Lost contact with EC2 after ${SSH_FAILURES} consecutive failed polls. Deployment outcome UNKNOWN - not reporting success."
        fi
        sleep "$POLL_INTERVAL"
        continue
    fi
    SSH_FAILURES=0

    case "$STATE" in
        "DONE 0")
            echo "::notice::Remote deployment script exited 0 (health checks passed on EC2)."
            exit 0
            ;;
        DONE\ *)
            fail "Remote deployment script failed with exit code ${STATE#DONE }. See the log above for the failing stage."
            ;;
        DEAD)
            fail "The remote deployment process disappeared without recording an exit status (killed externally, e.g. by the OOM killer or a reboot)."
            ;;
        NOPID)
            NOPID_POLLS=$(( NOPID_POLLS + 1 ))
            if (( NOPID_POLLS >= 3 )); then
                fail "The remote deployment state is missing (no process id recorded)."
            fi
            ;;
        RUNNING)
            NOPID_POLLS=0
            ;;
    esac
    sleep "$POLL_INTERVAL"
done
