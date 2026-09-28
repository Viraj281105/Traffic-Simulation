# AWS Free Tier Deployment Guide

This guide provides step-by-step instructions to deploy the Traffic Simulation project on AWS within the Free Tier. The process will take less than an hour and uses an EC2 instance running Docker and Docker Compose.

## 1. Prerequisites
- An AWS Account (within the first 12 months for Free Tier eligibility).
- Your project hosted on a Git repository (e.g., GitHub, GitLab) so you can clone it onto the server.

## 2. Launch an EC2 Instance

1. Go to the **AWS Management Console** and search for **EC2**.
2. Click **Instances** on the left menu, then click **Launch instances**.
3. **Name**: `Traffic-Simulation-Server` (or any name you prefer).
4. **Application and OS Images (AMI)**: Choose **Ubuntu**, and specifically select **Ubuntu Server 22.04 LTS (HVM)** or **24.04 LTS**. Ensure it says "Free tier eligible".
5. **Instance type**: Select **t2.micro** (or `t3.micro` depending on your region). This is Free Tier eligible.
6. **Key pair (login)**: 
   - Click **Create new key pair**.
   - Name it `traffic-sim-key`.
   - Key pair type: **RSA**.
   - Private key file format: **.pem** (for Mac/Linux/Windows 10+) or **.ppk** (if using PuTTY).
   - Click **Create key pair** (this will download a file to your computer. Keep it safe!).
7. **Network settings**:
   - Check **Allow SSH traffic from** -> **Anywhere 0.0.0.0/0** (or restrict to your IP for better security).
   - Check **Allow HTTP traffic from the internet** (Crucial: Your frontend uses port 80).
   - Check **Allow HTTPS traffic from the internet** (optional for now, good for later).
8. **Configure storage**: Leave it at 8 GiB gp2 (up to 30 GB is Free Tier eligible).
9. Click **Launch instance**.

## 3. Connect to your EC2 Instance

1. Once the instance state is "Running", click on the instance ID.
2. Find the **Public IPv4 address** (e.g., `54.234.xx.xx`).
3. Open your terminal (or PowerShell) on your local machine.
4. Change permissions of your downloaded key (Mac/Linux only):
   ```bash
   chmod 400 path/to/traffic-sim-key.pem
   ```
5. SSH into the instance:
   ```bash
   ssh -i "path/to/traffic-sim-key.pem" ubuntu@<YOUR_EC2_PUBLIC_IP>
   ```
   *Type `yes` if prompted about the fingerprint.*

## 4. Install Docker and Docker Compose

Run the following commands on your EC2 instance terminal:

```bash
# Update the package index
sudo apt update -y
sudo apt upgrade -y

# Install Docker
sudo apt install docker.io -y

# Start and enable Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add ubuntu user to the docker group so you don't need 'sudo' for docker commands
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo apt install docker-compose-v2 -y
```

> **Important**: Disconnect from the server (type `exit` and hit Enter) and SSH back in for the group changes to take effect.

```bash
# SSH back in
ssh -i "path/to/traffic-sim-key.pem" ubuntu@<YOUR_EC2_PUBLIC_IP>
```

Verify the installations:
```bash
docker --version
docker compose version
```

## 5. Clone Your Repository

You need to get your code onto the server. 
```bash
# If your repo is public:
git clone <YOUR_REPOSITORY_URL>
cd Traffic-Simulation

# If your repo is private, you can use a GitHub Personal Access Token or set up SSH keys on the server.
```

## 6. Configure Environment Variables

Create a `.env` file from the example or set your variables:
```bash
# Inside the Traffic-Simulation directory
touch .env
nano .env
```

Add your necessary environment variables. Based on `docker-compose.yml`, you might want to set an API Key for security:
```ini
API_KEY=your_super_secret_api_key_123
CORS_ORIGINS=http://<YOUR_EC2_PUBLIC_IP>
```
Press `Ctrl+O`, `Enter`, then `Ctrl+X` to save and exit nano.

## 7. Deploy the Application

Build and start the containers in detached mode:
```bash
docker compose up -d --build
```

Docker will pull the necessary base images, build your frontend and backend, and start them. 

## 8. Access the Application

1. Open your web browser.
2. Navigate to `http://<YOUR_EC2_PUBLIC_IP>`.

The frontend container maps port 80 to the internal 8080. Nginx (inside the frontend container) serves the web app and proxies `/api/` requests to the backend container seamlessly!

## Summary of Useful Commands

- View running containers: `docker ps`
- View backend logs: `docker compose logs -f backend`
- View frontend logs: `docker compose logs -f frontend`
- Stop the application: `docker compose down`
- Rebuild after pulling new changes: `docker compose up -d --build`
