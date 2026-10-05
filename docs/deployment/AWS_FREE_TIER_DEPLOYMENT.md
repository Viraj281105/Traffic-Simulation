# AWS EC2 Deployment Runbook

> **Status:** Current · V1.0 · step-by-step runbook for the deployment described in [Deployment & operations](README.md) (architecture, environment variables, verification, known issues — read §8 there before setting `API_KEY`).

This runbook deploys the containerized UrbanFlow stack (repository: Traffic-Simulation) to a single **Amazon EC2** instance with Docker Compose, sized for the AWS Free Tier.

---

## 1. Architecture & Resource Allocation

The application runs as a multi-container Docker stack orchestrated via Docker Compose:

```
                      Internet (Client Browsers)
                                  │
                                  ▼
                     AWS EC2 Instance (t2.micro / t3.micro)
                      ┌──────────────────────────────────────────────┐
                      │  Public IP / Domain (Port 80)                │
                      │                       │                      │
                      │                       ▼                      │
                      │  ┌────────────────────────────────────────┐  │
                      │  │       frontend Container (Nginx)       │  │
                      │  │   • Serves React Single Page App       │  │
                      │  │   • Proxies /api/ → backend:8000       │  │
                      │  │   • Proxies /ws/  → backend:8000 (WS)  │  │
                      │  │   • Memory limit: 128 MB (compose)     │  │
                      │  └───────────────────┬────────────────────┘  │
                      │                      │ Docker Internal Net   │
                      │                      ▼                       │
                      │  ┌────────────────────────────────────────┐  │
                      │  │       backend Container (FastAPI)      │  │
                      │  │   • Python 3.11 + Uvicorn engine       │  │
                      │  │   • IDM physics & real-time simulation │  │
                      │  │   • Memory limit: 512 MB (compose)     │  │
                      │  └───────────────────┬────────────────────┘  │
                      │                      │                       │
                      │                      ▼                       │
                      │  ┌────────────────────────────────────────┐  │
                      │  │      Named Docker Volume (EBS)         │  │
                      │  │   • /app/data/simulation.db            │  │
                      │  │   • Persistent replays & sweep results │  │
                      │  └────────────────────────────────────────┘  │
                      └──────────────────────────────────────────────┘
```

### Free Tier Resource Budget

| AWS Component | Free Tier Allowance | Our Stack Usage | Safety Margin |
| :--- | :--- | :--- | :--- |
| **Compute** | 750 hours/month of `t2.micro` or `t3.micro` | 1 instance running 24/7 (~730 hrs) | **100% Free** |
| **Memory** | 1.0 GB RAM total | Container limits 512 MB (backend) + 128 MB (frontend); 2 GB swap recommended | Check with `docker stats` |
| **Storage (EBS)**| 30 GB General Purpose SSD (gp3/gp2) | ~15–20 GB allocated for OS + Docker | **10+ GB Free** |
| **Data Transfer**| 100 GB/month outbound to internet | < 5 GB/month typical traffic | **95 GB Free** |

---

## 2. AWS Account & Cost Guardrails

To ensure your AWS bill stays strictly at **$0.00**, follow these rules:

1. **Set Up an AWS Budget Alert (MANDATORY)**:
   - Go to **AWS Billing Console** → **Budgets** → **Create Budget**.
   - Select **Zero spend budget** or set an alert threshold of **$0.01**.
   - Enter your email. AWS will notify you if any resource exceeds free tier limits.
2. **Run Only ONE Micro Instance**:
   - The 750 free hours cover exactly 1 instance running continuously for a full month (31 days × 24 hrs = 744 hrs).
   - If you start a second instance, both consume hours concurrently and will incur charges once 750 hours are exceeded.
3. **Elastic IP Caution**:
   - AWS charges for Elastic IPs (static public IPs) if they are **not attached to a running instance**. If you stop your instance, release any associated Elastic IP.
4. **EBS Volume Limit**:
   - The free tier covers up to 30 GB of total EBS across all volumes. Keep your root volume to **20 GB or 25 GB**.

---

## 3. Step 1: Provision the EC2 Instance

1. Log in to the [AWS Management Console](https://console.aws.amazon.com/) and navigate to **EC2**.
2. Click **Launch Instance**.
3. Configure the following parameters:
   - **Name**: `traffic-simulation-server`
   - **Application and OS Images (AMI)**: **Ubuntu Server 24.04 LTS (HVM), SSD Volume Type** (or Amazon Linux 2023). Both are free tier eligible.
   - **Architecture**: `64-bit (x86)`
   - **Instance Type**: `t2.micro` (or `t3.micro` in regions where t3.micro is the default free tier type).
   - **Key pair (login)**: Choose an existing key pair or create a new one (e.g., `traffic-key.pem`).
4. **Network Settings**:
   - Check **Allow SSH traffic from** → Select **My IP** (recommended for security) or `Anywhere (0.0.0.0/0)`.
   - Check **Allow HTTP traffic from the internet** (Port 80).
   - Check **Allow HTTPS traffic from the internet** (Port 443).
5. **Configure Storage**:
   - Set size to `25 GiB` of `gp3` or `gp2`.
6. Click **Launch Instance**.

---

## 4. Step 2: Configure Linux Swap (CRITICAL for 1 GB RAM)

> [!IMPORTANT]
> A `t2.micro` instance has only 1 GB of physical memory. During image builds or heavy simulation spikes, Linux will trigger the Out-Of-Memory (OOM) killer if swap space is absent. Allocating a 2 GB Swap file on EBS guarantees rock-solid stability.

Connect to your EC2 instance via SSH:
```bash
ssh -i /path/to/traffic-key.pem ubuntu@<EC2-PUBLIC-IP>
```

Run the following commands to initialize and activate a 2 GB Swap file:

```bash
# 1. Allocate a 2GB file
sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048

# 2. Secure the file permissions
sudo chmod 600 /swapfile

# 3. Format as swap
sudo mkswap /swapfile

# 4. Activate swap
sudo swapon /swapfile

# 5. Make swap persistent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 6. Optimize swappiness (10 is ideal for servers)
sudo sysctl vm.swappiness=10
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf

# 7. Verify memory and swap
free -h
```
You should see:
```
               total        used        free      shared  buff/cache   available
Mem:           961Mi       120Mi       550Mi       1.0Mi       291Mi       710Mi
Swap:          2.0Gi          0B       2.0Gi
```

---

## 5. Step 3: Install Docker & Docker Compose

Run the official Docker convenience script:

```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Allow the ubuntu user to run Docker without sudo
sudo usermod -aG docker $USER

# Apply group changes immediately (or log out and log back in)
newgrp docker

# Verify installation
docker --version
docker compose version
```

---

## 6. Step 4: Deploy the Application

There are two deployment methods:

### Method A: Direct Git Clone & Build (Recommended for First-Time Setup)

```bash
# 1. Clone repository
git clone https://github.com/Viraj281105/Traffic-Simulation.git
cd Traffic-Simulation

# 2. Build and launch all containers in detached mode
#    (GIT_COMMIT records the code version with every saved run)
GIT_COMMIT=$(git rev-parse HEAD) docker compose up -d --build

# 3. Check running status and health
docker compose ps
```

Both services (`backend`, `frontend`) should report a **healthy** status; the frontend starts only after the backend is healthy.

Now open your web browser and navigate to:
```
http://<YOUR-EC2-PUBLIC-IP>                 # landing page
http://<YOUR-EC2-PUBLIC-IP>/app/comparative # guided comparison
```

---

### Method B: Pre-built images (optional, not set up in this repository)

To avoid building on a small instance, build the images elsewhere and push them to a registry. The repository's CI builds images but does not publish them; this method needs your own registry and a Compose override that references the image tags:

1. On your local machine / CI:
   ```bash
   docker build -t yourusername/traffic-backend:latest -f backend/Dockerfile .
   docker build -t yourusername/traffic-frontend:latest ./frontend

   docker push yourusername/traffic-backend:latest
   docker push yourusername/traffic-frontend:latest
   ```

2. On the EC2 instance, update `docker-compose.yml` to reference the image tags and simply run:
   ```bash
   docker compose pull
   docker compose up -d
   ```

---

## 7. Step 5: Data Persistence & Backups

The SQLite database (`simulation.db`) stores:
- Saved runs and replays (with their reproducibility records)
- Per-tick metric timelines
- Volume-sweep sessions and their runs

The database is mapped to a named Docker volume (`traffic_data`) located on the EC2 host at `/var/lib/docker/volumes/traffic-simulation_traffic_data/_data/simulation.db`.

### Creating a Manual Backup

```bash
# Create a local backup folder
mkdir -p ~/backups

# Copy database snapshot
docker compose exec backend cp /app/data/simulation.db /app/data/simulation.db.bak
docker cp $(docker compose ps -q backend):/app/data/simulation.db.bak ~/backups/simulation_$(date +%Y%m%d).db
```

---

## 8. Step 6: Custom Domain & Free SSL (HTTPS)

### Option 1: Cloudflare CDN (Easiest, Free SSL, DDoS Protection)
1. Add your custom domain to Cloudflare (Free plan).
2. Add an **A Record** pointing `@` and `www` to your EC2 Public IP.
3. Enable the **Cloudflare Proxy (Orange Cloud)**.
4. Set SSL mode to **Flexible** (or Full with self-signed certificate).
5. Your site is now live on `https://yourdomain.com` with free automated SSL and CDN caching!

### Option 2: Let's Encrypt / Certbot directly on EC2
Certbot can obtain certificates on the instance, but **the checked-in nginx template has no TLS server block** (it listens on 8080 only, published on host port 80). Serving HTTPS from the instance therefore needs an additional nginx configuration and a 443 port mapping that are not part of this repository.

---

## 9. Day-to-Day Operations & Monitoring

### Viewing Logs
```bash
# Stream all logs
docker compose logs -f

# View backend simulation logs
docker compose logs -f backend

# View Nginx access & error logs
docker compose logs -f frontend
```

### Checking Resource Usage
```bash
# View live container CPU & RAM consumption
docker stats --no-stream
```
Compare usage with the Compose limits (backend 512 MB, frontend 128 MB). Study workers add roughly 40 MB each; lower `STUDY_WORKERS` on small instances.

### Updating to the Latest Version
```bash
cd ~/Traffic-Simulation
git pull origin main
GIT_COMMIT=$(git rev-parse HEAD) docker compose up -d --build
```

### Stopping or Restarting
```bash
# Restart without wiping data
docker compose restart

# Stop all containers
docker compose down

# Stop and remove persistent data (CAUTION: wipes database)
docker compose down -v
```

---

## 10. Summary Checklist for AWS Free Tier Deployment

- [x] AWS Budget alert created at $0.01 threshold.
- [x] Only one `t2.micro` or `t3.micro` instance active.
- [x] Security Group open on port 80 (and 22 restricted to your IP).
- [x] 2 GB Swap file configured and enabled via `/etc/fstab`.
- [x] Docker and Docker Compose v2 installed.
- [x] Frontend reverse-proxying `/api/` and `/ws/` through port 80.
- [x] Database mounted to persistent volume `traffic_data`.
- [x] Application verified reachable at `http://<EC2-PUBLIC-IP>` (see the verification table in [Deployment & operations §6](README.md#6-verify-the-deployment)).
- [x] `API_KEY` set to a long random value in `.env` (nginx supplies it to the backend; see [Deployment & operations §4](README.md#4-environment-configuration)).
