#!/usr/bin/env bash
# ==============================================================================
# UrbanFlow / Traffic-Simulation: EC2 Production Deployment Script
# ==============================================================================
# Idempotent deployment script executed on the AWS EC2 instance.
#
# Steps:
#   1. Acquire execution lock to prevent concurrent deployments.
#   2. Validate local environment (Git, Docker, Compose v2) and check host
#      resources (free disk is enforced; memory/swap is reported).
#   3. Fetch and checkout the target commit on the deployment branch.
#   4. Rebuild images one service at a time with the GIT_COMMIT build argument
#      (without stopping containers).
#   5. Recreate and restart containers safely (preserving persistent SQLite volume).
#   6. Safely prune obsolete dangling images.
#   7. Run post-deployment health checks against /health, /, and /api/version.
#   8. Attempt safe rollback to previous commit if health check fails.
# ==============================================================================

set -Eeuo pipefail

# --- Default Configuration ---
REPO_DIR="${HOME}/Traffic-Simulation"
DEPLOY_BRANCH="deployment"
TARGET_COMMIT=""
HEALTH_TIMEOUT=60
HTTP_PORT=""
SKIP_HEALTH_CHECK=0
LOCK_FILE="/tmp/urbanflow-deploy.lock"
# Minimum free space (MB) on the Docker data filesystem required to start a build.
MIN_FREE_DISK_MB="${MIN_FREE_DISK_MB:-2048}"

# --- Helper Functions ---
log_info() {
    echo -e "\033[1;34m[INFO]\033[0m $*"
}

log_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $*"
}

log_warn() {
    echo -e "\033[1;33m[WARN]\033[0m $*"
}

log_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $*" >&2
}

# --- Failure diagnostics ---
# CURRENT_STAGE records where the script was, so a failure (or a signal from a
# dropped SSH session / killed parent) is attributable to a stage in the log.
CURRENT_STAGE="startup"

on_err() {
    local rc=$1 line=$2 cmd=$3
    log_error "Command failed (exit $rc) at line $line during stage '$CURRENT_STAGE': $cmd"
}

on_exit() {
    local rc=$?
    if [[ $rc -ne 0 ]]; then
        log_error "Deployment script exiting with status $rc during stage: $CURRENT_STAGE"
    fi
}

on_signal() {
    log_error "Received signal $1 during stage '$CURRENT_STAGE'. The deployment was interrupted."
    exit "$2"
}

trap 'on_err "$?" "$LINENO" "$BASH_COMMAND"' ERR
trap on_exit EXIT
trap 'on_signal SIGHUP 129' HUP
trap 'on_signal SIGINT 130' INT
trap 'on_signal SIGTERM 143' TERM

# Log memory, swap and disk so build-time resource pressure shows up in the CI log.
log_resources() {
    log_info "Host resources ($1):"
    if command -v free >/dev/null 2>&1; then free -m | sed 's/^/    /'; fi
    df -Pm / 2>/dev/null | sed 's/^/    /' || true
}

# Fail early if the disk is nearly full (builds would die half-way through);
# only warn about memory, since low memory without swap is a risk, not a fact.
check_host_resources() {
    local docker_root free_mb mem_mb swap_mb
    docker_root=$($DOCKER_CMD info --format '{{.DockerRootDir}}' 2>/dev/null || echo "/")
    free_mb=$(df -Pm "$docker_root" 2>/dev/null | awk 'NR==2 {print $(NF-2)}' || true)
    if [[ -z "$free_mb" ]]; then
        free_mb=$(df -Pm / 2>/dev/null | awk 'NR==2 {print $(NF-2)}' || true)
    fi
    if [[ -n "$free_mb" ]]; then
        log_info "Free disk for Docker data: ${free_mb} MB (minimum ${MIN_FREE_DISK_MB} MB)"
        if [[ "$free_mb" -lt "$MIN_FREE_DISK_MB" ]]; then
            log_error "Only ${free_mb} MB free; at least ${MIN_FREE_DISK_MB} MB is required to build images."
            log_error "Free space (e.g. 'docker image prune', 'docker builder prune') and redeploy. Nothing was changed."
            exit 1
        fi
    else
        log_warn "Could not determine free disk space; continuing."
    fi
    if [[ -r /proc/meminfo ]]; then
        mem_mb=$(awk '/^MemTotal:/ {printf "%d", $2/1024}' /proc/meminfo)
        swap_mb=$(awk '/^SwapTotal:/ {printf "%d", $2/1024}' /proc/meminfo)
        log_info "Memory: ${mem_mb} MB RAM, ${swap_mb} MB swap"
        if [[ "$mem_mb" -lt 1500 && "$swap_mb" -eq 0 ]]; then
            log_warn "Low memory and NO swap: the frontend build (tsc + vite) can exhaust RAM, freeze the host and drop SSH."
            log_warn "Configure the 2 GB swap file described in docs/deployment/AWS_FREE_TIER_DEPLOYMENT.md section 4."
        fi
    fi
}

show_help() {
    cat << 'EOF'
Usage: deploy-ec2.sh [OPTIONS]

Options:
  --commit <SHA>          Target Git commit SHA to deploy (default: HEAD of deployment branch)
  --repo-dir <PATH>       Path to cloned repository on EC2 (default: ~/Traffic-Simulation)
  --branch <NAME>         Git deployment branch name (default: deployment)
  --http-port <PORT>      Host HTTP port to probe for health check (default: from .env or 80)
  --health-timeout <SEC>  Maximum seconds to wait for health check (default: 60)
  --skip-health-check     Skip post-deployment HTTP health check
  --help                  Show this help message and exit
EOF
}

# --- Parse Arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --commit)
            TARGET_COMMIT="$2"
            shift 2
            ;;
        --repo-dir)
            REPO_DIR="$2"
            shift 2
            ;;
        --branch)
            DEPLOY_BRANCH="$2"
            shift 2
            ;;
        --http-port)
            HTTP_PORT="$2"
            shift 2
            ;;
        --health-timeout)
            HEALTH_TIMEOUT="$2"
            shift 2
            ;;
        --skip-health-check)
            SKIP_HEALTH_CHECK=1
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Expand tilde in REPO_DIR if present
REPO_DIR="${REPO_DIR/#\~/$HOME}"

# --- 1. Concurrency Control (Lock File) ---
CURRENT_STAGE="acquiring deployment lock"
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    log_error "Another deployment is currently running on this EC2 instance. Aborting to prevent race condition."
    exit 1
fi

log_info "Starting UrbanFlow production deployment..."
log_info "Target Directory: $REPO_DIR"
log_info "Target Branch:    $DEPLOY_BRANCH"
if [[ -n "$TARGET_COMMIT" ]]; then
    log_info "Target Commit:    $TARGET_COMMIT"
else
    log_info "Target Commit:    Latest commit on origin/$DEPLOY_BRANCH"
fi

# --- 2. Environment & Prerequisites Validation ---
CURRENT_STAGE="validating environment"
if ! command -v git >/dev/null 2>&1; then
    log_error "git is not installed on this system."
    exit 1
fi

if [[ ! -d "$REPO_DIR" ]]; then
    log_error "Repository directory not found at: $REPO_DIR"
    log_error "Please ensure the repository is cloned on EC2 before deploying."
    exit 1
fi

cd "$REPO_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log_error "$REPO_DIR is not a valid Git repository."
    exit 1
fi

# Determine Docker command (with or without sudo)
if docker info >/dev/null 2>&1; then
    DOCKER_CMD="docker"
elif sudo docker info >/dev/null 2>&1; then
    DOCKER_CMD="sudo docker"
    log_warn "Running Docker with sudo. Consider adding user to 'docker' group: sudo usermod -aG docker \$USER"
else
    log_error "Docker is not running or current user lacks docker permissions."
    exit 1
fi

# Verify Docker Compose v2 availability
if ! $DOCKER_CMD compose version >/dev/null 2>&1; then
    log_error "Docker Compose v2 ('docker compose') is not available."
    exit 1
fi

# Check for production .env file
if [[ -f ".env" ]]; then
    log_info "Detected production environment file: .env"
    # Infer port if not explicitly passed
    if [[ -z "$HTTP_PORT" ]]; then
        INFERRED_PORT=$(grep -E '^URBANFLOW_HTTP_PORT=' .env | cut -d '=' -f2 | tr -d ' "\r' || true)
        if [[ -n "$INFERRED_PORT" ]]; then
            HTTP_PORT="$INFERRED_PORT"
        fi
    fi
else
    log_warn "No .env file found at $REPO_DIR/.env."
    log_warn "Running with default environment configuration. Ensure required secrets are configured."
fi

# Default HTTP port if still unset
HTTP_PORT="${HTTP_PORT:-80}"
log_info "Health check probe port: $HTTP_PORT"

# Host resource preflight (before any repository or container state is touched)
log_resources "before deployment"
check_host_resources

# --- 3. Git Fetch and Checkout ---
CURRENT_STAGE="fetching and checking out target commit"
log_info "Fetching latest changes from origin..."
git fetch origin "$DEPLOY_BRANCH"

PREVIOUS_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "")
log_info "Previous deployed commit: ${PREVIOUS_COMMIT:-none}"

# Switch to the deployment branch if not already on it
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [[ "$CURRENT_BRANCH" != "$DEPLOY_BRANCH" ]]; then
    log_info "Switching to $DEPLOY_BRANCH branch..."
    git checkout "$DEPLOY_BRANCH"
fi

if [[ -n "$TARGET_COMMIT" ]]; then
    log_info "Resetting working copy to exact commit: $TARGET_COMMIT..."
    git reset --hard "$TARGET_COMMIT"
else
    log_info "Pulling latest $DEPLOY_BRANCH changes..."
    git pull origin "$DEPLOY_BRANCH"
fi

DEPLOYED_COMMIT=$(git rev-parse HEAD)
log_info "Active commit for deployment: $DEPLOYED_COMMIT"

# --- 4. Build Images (Safe Pre-flight Build) ---
# Building images while old containers remain running prevents downtime if build fails.
# Services are built one at a time: 'docker compose build' otherwise builds the
# backend and frontend in parallel, and the frontend's `tsc && vite build` is the
# memory-hungry step on a 1 GB instance. Building sequentially lowers peak memory.
CURRENT_STAGE="building images"
log_info "Building Docker images (GIT_COMMIT=$DEPLOYED_COMMIT), one service at a time..."
BUILD_SERVICES=$($DOCKER_CMD compose config --services)
for SERVICE in $BUILD_SERVICES; do
    CURRENT_STAGE="building image: $SERVICE"
    log_info "Building service '$SERVICE'..."
    BUILD_START=$SECONDS
    if ! GIT_COMMIT="$DEPLOYED_COMMIT" $DOCKER_CMD compose build "$SERVICE"; then
        log_error "Docker build of '$SERVICE' failed after $((SECONDS - BUILD_START))s! Aborting deployment. Existing containers remain running."
        log_resources "after failed build"
        exit 1
    fi
    log_info "Service '$SERVICE' built in $((SECONDS - BUILD_START))s."
done
log_success "Docker images built successfully."
log_resources "after build"

# --- Rollback Helper Function ---
perform_rollback() {
    CURRENT_STAGE="rollback"
    log_error "Deployment failed! Initiating rollback procedure..."
    if [[ -n "$PREVIOUS_COMMIT" && "$PREVIOUS_COMMIT" != "$DEPLOYED_COMMIT" ]]; then
        log_warn "Attempting automated rollback to previous commit: $PREVIOUS_COMMIT..."
        git checkout "$PREVIOUS_COMMIT"
        if GIT_COMMIT="$PREVIOUS_COMMIT" $DOCKER_CMD compose up -d --build; then
            log_warn "Containers rolled back to previous commit $PREVIOUS_COMMIT."
            log_warn "Stack is running previous version. Inspect logs to diagnose why $DEPLOYED_COMMIT failed."
        else
            log_error "Automated rollback also failed. Manual operator intervention required immediately!"
        fi
    else
        log_warn "No previous commit available for automated rollback. Stack left in current state for inspection."
    fi
    exit 1
}

# --- 5. Recreate & Restart Containers ---
CURRENT_STAGE="recreating containers"
# Persistent volume 'traffic_data' (/app/data/simulation.db) is preserved by docker compose up.
log_info "Recreating containers with new images..."
if ! GIT_COMMIT="$DEPLOYED_COMMIT" $DOCKER_CMD compose up -d --remove-orphans; then
    log_error "Failed to start containers with 'docker compose up -d'!"
    perform_rollback
fi
log_success "Containers recreated and running in detached mode."

# --- 6. Prune Dangling Images Safely ---
CURRENT_STAGE="pruning dangling images"
# Cleans only untagged dangling build layers; active images and persistent volumes are untouched.
log_info "Pruning obsolete dangling Docker images..."
$DOCKER_CMD image prune -f >/dev/null 2>&1 || true

# --- 7. Post-Deployment Health Check ---
CURRENT_STAGE="post-deployment health check"
if [[ "$SKIP_HEALTH_CHECK" -eq 1 ]]; then
    log_warn "Health check skipped by user flag."
else
    log_info "Running post-deployment health checks (timeout: ${HEALTH_TIMEOUT}s)..."
    HEALTHY=0
    ELAPSED=0
    INTERVAL=3

    HEALTH_URL="http://127.0.0.1:${HTTP_PORT}/health"
    ROOT_URL="http://127.0.0.1:${HTTP_PORT}/"
    VERSION_URL="http://127.0.0.1:${HTTP_PORT}/api/version"

    while [[ $ELAPSED -lt $HEALTH_TIMEOUT ]]; do
        # Check backend health proxied through frontend
        BACKEND_STATUS=""
        if command -v curl >/dev/null 2>&1; then
            BACKEND_STATUS=$(curl -s -m 5 "$HEALTH_URL" 2>/dev/null || echo "")
            ROOT_CODE=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "$ROOT_URL" 2>/dev/null || echo "000")
        elif command -v wget >/dev/null 2>&1; then
            BACKEND_STATUS=$(wget -q -O - -T 5 "$HEALTH_URL" 2>/dev/null || echo "")
            ROOT_CODE=$(wget -q -S -O /dev/null -T 5 "$ROOT_URL" 2>&1 | grep "HTTP/" | awk '{print $2}' | tail -1 || echo "000")
        else
            # Python fallback
            BACKEND_STATUS=$(python3 -c "import urllib.request; print(urllib.request.urlopen('$HEALTH_URL', timeout=5).read().decode())" 2>/dev/null || echo "")
            ROOT_CODE=$(python3 -c "import urllib.request; print(urllib.request.urlopen('$ROOT_URL', timeout=5).getcode())" 2>/dev/null || echo "000")
        fi

        if [[ "$BACKEND_STATUS" =~ "healthy" ]] && [[ "$ROOT_CODE" == "200" ]]; then
            log_success "Health check passed at tick ${ELAPSED}s! Backend is healthy and frontend returned HTTP 200."
            HEALTHY=1
            break
        fi

        log_info "Waiting for services to become healthy... ($ELAPSED/${HEALTH_TIMEOUT}s)"
        sleep "$INTERVAL"
        ELAPSED=$((ELAPSED + INTERVAL))
    done

    if [[ "$HEALTHY" -ne 1 ]]; then
        log_error "Post-deployment health check timed out after ${HEALTH_TIMEOUT}s!"
        log_error "Recent container statuses:"
        $DOCKER_CMD compose ps -a
        log_error "Recent container logs:"
        $DOCKER_CMD compose logs --tail=100
        perform_rollback
    fi

    # Report build provenance version if available
    if command -v curl >/dev/null 2>&1; then
        VERSION_INFO=$(curl -s -m 5 "$VERSION_URL" 2>/dev/null || echo "")
        if [[ -n "$VERSION_INFO" ]]; then
            log_info "Reported deployment version: $VERSION_INFO"
        fi
    fi
fi

# --- 8. Final Status Report ---
CURRENT_STAGE="final status report"
log_success "=========================================================="
log_success "UrbanFlow production deployment completed successfully!"
log_success "Deployed Commit: $DEPLOYED_COMMIT"
log_success "Compose Status:"
$DOCKER_CMD compose ps
log_success "=========================================================="

exit 0
