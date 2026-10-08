# Production CI/CD Setup

> **Audience:** Khushi (DevOps / Production Infrastructure Lead)  
> **Repository:** `Viraj281105/Traffic-Simulation`  
> **Scope:** Automated deployment pipeline from GitHub (`deployment` branch) to AWS EC2 via GitHub Actions and Docker Compose.

---

## 1. Purpose

The objective of this pipeline is to provide a zero-manual-intervention production deployment workflow for UrbanFlow. Once EC2 is provisioned, powered on, and the one-time configuration is complete, deploying new production releases requires only merging `main` into the dedicated `deployment` branch:

```text
main
  ↓
merge into deployment
  ↓
GitHub Actions (.github/workflows/deploy.yml)
  ↓
SSH to EC2
  ↓
checkout deployment
  ↓
Docker Compose rebuild (GIT_COMMIT=$(git rev-parse HEAD))
  ↓
restart services (zero data loss on traffic_data volume)
  ↓
health check (/health, /, /api/version)
  ↓
LIVE UrbanFlow
```

> [!IMPORTANT]
> **Operational Rule:** After one-time setup, normal production deployment requires **only**:
> ```text
> Merge main → deployment
> ```
> Developers and operators do **not** need to manually SSH into the EC2 instance or run Docker commands for standard deployments.

---

## 2. One-Time GitHub Configuration

Khushi must create repository secrets in GitHub to allow GitHub Actions to authenticate securely to the EC2 instance.

### Navigation

1. In GitHub, open the repository: `https://github.com/Viraj281105/Traffic-Simulation`
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each required item below:

| Secret | Purpose | Value to provide | Required / Optional |
|---|---|---|---|
| `EC2_HOST` | EC2 Public IP or DNS hostname | `KHUSHI ACTION:` Provide EC2 public IPv4 (e.g. `<EC2_PUBLIC_IP>` or `<EC2_PUBLIC_DNS>`) | **Required** |
| `EC2_USER` | SSH username | `KHUSHI ACTION:` Typically `ubuntu` (for Ubuntu AMIs) or `ec2-user` (for Amazon Linux) | **Required** |
| `EC2_SSH_PRIVATE_KEY` | Private SSH key (PEM format) | `KHUSHI ACTION:` Full contents of your `.pem` key file including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----` | **Required** |
| `EC2_SSH_PORT` | SSH daemon port on EC2 | `22` (default unless custom port configured) | Optional (defaults to `22`) |
| `EC2_DEPLOY_PATH` | Path where repo is cloned on EC2 | `/home/ubuntu/Traffic-Simulation` or `~/Traffic-Simulation` | Optional (defaults to `~/Traffic-Simulation`) |

> [!CAUTION]
> **DO NOT COMMIT SECRETS:** Never paste private keys, IP addresses, or secrets directly into repository files or issues. GitHub Actions automatically masks secrets in workflow logs.

---

## 3. EC2 One-Time Setup

The EC2 instance acts as the Docker host for the UrbanFlow application. Follow these setup steps on the target EC2 machine.

### A. System & Package Requirements (`KHUSHI ACTION`)

Connect to the instance via SSH:
```bash
ssh -i /path/to/traffic-key.pem <EC2_USER>@<EC2_HOST>
```

Update system packages and install Git, Curl, and utilities:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates
```

### B. Linux Swap Configuration (CRITICAL for 1 GB RAM Micro Instances)

If using a `t2.micro` or `t3.micro` instance (1 GB RAM), a 2 GB swap file prevents Out-Of-Memory (OOM) errors during Docker builds:
```bash
# Allocate swap if not already present (KHUSHI: VERIFY)
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    sudo sysctl vm.swappiness=10
    echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
fi

# Verify swap is active
free -h
```

### C. Docker & Docker Compose v2 Installation

Install Docker Engine and Docker Compose v2:
```bash
# Install Docker via official convenience script
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
rm -f get-docker.sh

# Add the EC2 user to the docker group so sudo is not needed
sudo usermod -aG docker $USER

# Apply group membership immediately
newgrp docker
```

Verify Docker and Compose:
```bash
# Verify Docker works without sudo (KHUSHI: VERIFY)
docker --version
docker compose version
```

### D. Repository Clone & Branch Setup

Clone the repository into the user's home directory (`~/Traffic-Simulation`):
```bash
cd ~
if [ ! -d "Traffic-Simulation" ]; then
    git clone https://github.com/Viraj281105/Traffic-Simulation.git
fi

cd ~/Traffic-Simulation
```

Ensure the repository tracks the dedicated `deployment` branch:
```bash
# Fetch all remote branches
git fetch origin

# Switch to the deployment branch (KHUSHI: VERIFY)
git checkout deployment || git checkout -b deployment origin/deployment

# Confirm current branch is deployment
git branch --show-current
# Expected output: deployment
```

### E. SSH Public Key Authorization (`KHUSHI: VERIFY`)

Ensure the public key corresponding to `EC2_SSH_PRIVATE_KEY` is present in:
```bash
~/.ssh/authorized_keys
```
Ensure permissions are strict:
```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

### F. AWS Security Group Firewall Ports (`KHUSHI: VERIFY`)

Verify that the EC2 Security Group inbound rules permit:
- **Port 22 (SSH):** Inbound from GitHub Actions runner IP range (or administrator IP).
- **Port 80 (HTTP):** Inbound from client browsers (`0.0.0.0/0` or reverse proxy/CDN).
- **Port 443 (HTTPS):** Inbound if TLS termination is configured upstream.

---

## 4. Production Environment Variables

UrbanFlow separates non-sensitive defaults from production secrets.

### Safe to Commit (Already in repository)
- Default container ports (`8080` internally, `80` on host)
- Memory limits in `docker-compose.yml` (`512M` backend, `128M` frontend)
- Health check configurations
- Schema paths and build scripts

### Must Remain on EC2 / GitHub Secrets (`DO NOT COMMIT`)

Create `~/Traffic-Simulation/.env` on the EC2 host. This file is excluded from Git via `.gitignore` and must **never** be checked into version control.

```bash
# KHUSHI ACTION: Create ~/Traffic-Simulation/.env on EC2
cat << 'EOF' > ~/Traffic-Simulation/.env
# ==============================================================================
# UrbanFlow Production Environment Configuration (EC2 ONLY)
# ==============================================================================

# Internal backend bearer token / nginx proxy key (long random hex string)
# Generate with: openssl rand -hex 32
API_KEY=<KHUSHI_GENERATE_LONG_HEX_SECRET>

# Allowed CORS origins (set to your public host or custom domain)
CORS_ORIGINS=http://<EC2_PUBLIC_IP>,http://localhost

# Study runner worker count (1-2 recommended on micro instances)
STUDY_WORKERS=2

# Host HTTP port override (default: 80)
URBANFLOW_HTTP_PORT=80
URBANFLOW_ALT_HTTP_PORT=3000

# Optional AWS Cognito configuration (if user sign-in is enabled)
# COGNITO_USER_POOL_ID=<POOL_ID>
# COGNITO_CLIENT_ID=<CLIENT_ID>
# AWS_REGION=<REGION>
EOF

chmod 600 ~/Traffic-Simulation/.env
```

---

## 5. Production URL Configuration

| Value | Where configured | Who provides it | Purpose |
|---|---|---|---|
| **Frontend URL** | Web browser / DNS | Khushi | `http://<EC2_PUBLIC_IP>/` or custom domain |
| **Backend/API URL** | Handled automatically by Nginx reverse proxy | Automatic (in-container proxy `/api/`) | Client calls `http://<EC2_PUBLIC_IP>/api/*` |
| **WebSocket URL** | Handled automatically by Nginx reverse proxy | Automatic (in-container proxy `/ws/`) | Client calls `ws://<EC2_PUBLIC_IP>/ws/*` |
| **EC2 Host** | GitHub Action Secret `EC2_HOST` | Khushi | SSH target host for CI/CD |

---

## 6. First Deployment

Follow this checklist to perform the first deployment through the automated pipeline:

1. [ ] **Configure GitHub Secrets:** Enter `EC2_HOST`, `EC2_USER`, and `EC2_SSH_PRIVATE_KEY` in GitHub.
2. [ ] **Complete EC2 Prerequisites:** Verify Docker, Docker Compose v2, and swap are active on EC2.
3. [ ] **Verify Local Docker Compose on EC2:**
   ```bash
   cd ~/Traffic-Simulation
   GIT_COMMIT=$(git rev-parse HEAD) docker compose up -d --build
   docker compose ps
   # Verify both containers report "healthy"
   ```
4. [ ] **Verify `deployment` branch exists:**
   ```bash
   # On your local machine or in GitHub UI:
   git push origin main:deployment
   ```
5. [ ] **Trigger First CI/CD Pipeline Run:**
   - Either make a commit/merge to `deployment`, OR
   - Go to GitHub → **Actions** → **Production EC2 Deployment** → **Run workflow** (branch: `deployment`).
6. [ ] **Monitor Deployment Execution:**
   - Open the running workflow in GitHub Actions.
   - Confirm SSH authentication, script transfer, image build, container restart, and health checks pass.
7. [ ] **Verify Live Application in Browser:**
   - Open `http://<EC2_PUBLIC_IP>/` (landing page should load).
   - Open `http://<EC2_PUBLIC_IP>/app/comparative` (dashboard should load).
   - Test a live simulation comparison (verifies WebSockets and backend engine).
   - Verify health: `curl -s http://<EC2_PUBLIC_IP>/health` returns `{"status":"healthy"}`.
   - Verify version: `curl -s http://<EC2_PUBLIC_IP>/api/version` returns the deployed Git commit SHA.

---

## 7. Normal Deployment

Once initial setup is verified, standard production deployment follows this streamlined path:

```text
Developer changes
      ↓
main (tested & merged via PR)
      ↓
Merge main → deployment
      ↓
GitHub Actions automatically triggers
      ↓
EC2 automatically pulls, rebuilds, and restarts
      ↓
Production updated & verified
```

> [!NOTE]
> Developers and operators **must not** manually SSH into EC2 for normal deployments. The automated pipeline enforces commit traceability and health-check verification.

---

## 8. Manual Deployment

If you need to redeploy without a branch commit (for example, following an EC2 instance stop/start, or to redeploy a specific previous commit):

1. Go to **Actions** tab in GitHub.
2. Select **Production EC2 Deployment** in the left sidebar.
3. Click **Run workflow**.
4. Select branch: `deployment`.
5. (Optional) Provide a specific commit SHA in `target_commit`, or leave blank to deploy the latest commit on `deployment`.
6. Click the green **Run workflow** button.

---

## 9. Monitoring

### GitHub Actions Logs
- Open **Actions** tab → click the latest workflow run under **Production EC2 Deployment**.
- Expand the **Execute Deployment & Verification** step to view the complete build log, container restart events, and health check output.

### Emergency Inspection via SSH
If a deployment reports an issue, connect directly to EC2:
```bash
ssh -i /path/to/traffic-key.pem <EC2_USER>@<EC2_HOST>
cd ~/Traffic-Simulation
```

### Useful Diagnostic Commands
```bash
# 1. View running container statuses and healthcheck results
docker compose ps

# 2. Follow live backend simulation logs
docker compose logs -f backend

# 3. Follow live frontend/nginx logs
docker compose logs -f frontend

# 4. View container resource consumption (RAM / CPU)
docker stats --no-stream

# 5. Probe healthcheck locally on EC2
curl -i http://localhost/health

# 6. Verify deployed code commit
curl -s http://localhost/api/version
```

---

## 10. Failure / Recovery

### Scenario A: Docker Build Fails
- **Behavior:** The deployment script builds new images with `docker compose build` **before** stopping or restarting any containers. If compilation or build steps fail, existing containers are **never touched**.
- **Action:** The GitHub Action fails. Check the build step log in GitHub Actions to fix the Dockerfile or dependency issue.

### Scenario B: Health Check Fails
- **Behavior:** If newly started containers fail to become healthy within 60 seconds (e.g. startup crash), `scripts/deploy-ec2.sh` automatically prints the last 100 log lines from both containers.
- **Automated Rollback:** The script automatically attempts to revert to the previous Git commit and restarts the previous containers.
- **GitHub Status:** The GitHub Action still fails loudly with a non-zero exit code to alert the team.

### Scenario C: EC2 is Unreachable
- **Behavior:** If the EC2 instance is stopped, rebooting, or security groups block port 22, GitHub Actions fails at the `Verify SSH Connectivity` step with a clear error annotation.
- **Action:** Confirm in AWS Console that the EC2 instance is in `running` state and verify its public IP address has not changed (unless using an Elastic IP).

### Scenario D: Manual Rollback Procedure
If automated rollback does not resolve an issue or you need to revert to a known good release manually:

```bash
# Connect to EC2
ssh -i /path/to/traffic-key.pem <EC2_USER>@<EC2_HOST>
cd ~/Traffic-Simulation

# Checkout the known good commit or tag
git checkout <KNOWN_GOOD_COMMIT_SHA>

# Rebuild and restart the stack
GIT_COMMIT=$(git rev-parse HEAD) docker compose up -d --build

# Verify container health
docker compose ps
curl -i http://localhost/health
```

---

## 11. Security Rules

1. **Never Commit Private Keys:** Private SSH keys (`.pem`) must exist only in GitHub Secrets (`EC2_SSH_PRIVATE_KEY`) and the operator's secure workstation.
2. **Never Commit Production `.env`:** The file `~/Traffic-Simulation/.env` contains production keys and is git-ignored.
3. **Never Output Secrets to Logs:** Ensure deployment scripts never echo secret strings or tokens.
4. **Minimal Security Group Exposure:** Restrict inbound SSH (Port 22) to authorized administrative IP ranges or GitHub Actions IPs where practical.
5. **Protect the SQLite Volume:** Never run `docker compose down -v` on production. The named volume `traffic_data` stores simulation runs, replay records, and database state.
6. **Credential Rotation:** If an SSH key or `API_KEY` is suspected of compromise, rotate it immediately in AWS and update GitHub Secrets.

---

## 12. Verification Checklist

Complete this checklist during initial handoff verification:

- [ ] GitHub Actions Secrets configured (`EC2_HOST`, `EC2_USER`, `EC2_SSH_PRIVATE_KEY`)
- [ ] EC2 SSH access verified with provided key
- [ ] 2 GB Swap verified on EC2 (`free -h`)
- [ ] Docker and Docker Compose v2 verified (`docker compose version`)
- [ ] Production `.env` file created on EC2 at `~/Traffic-Simulation/.env`
- [ ] Dedicated `deployment` branch exists on GitHub
- [ ] GitHub Actions detects `.github/workflows/deploy.yml`
- [ ] First deployment triggered and completes successfully
- [ ] Post-deployment health check passes (`curl -s http://<EC2_HOST>/health`)
- [ ] Frontend landing page loads (`http://<EC2_HOST>/`)
- [ ] Guided comparative simulation runs successfully
- [ ] WebSocket streaming works in browser
- [ ] Deployment logs reviewed in GitHub Actions
- [ ] Failure and rollback procedure understood
