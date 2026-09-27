# AWS Free Tier Deployment Plan

This document outlines the strategy for deploying the entire Traffic Simulation project (Frontend, Landing Page, Backend, and Database) to AWS using strictly the **12-Month Free Tier**. 

## Proposed Architecture (Per Account)

We will use standard, highly reliable AWS services that fall under the free tier.

### 1. Frontend & Landing Page (Static Hosting)
- **Services**: AWS S3 + AWS CloudFront
- **Free Tier Allowance**: 
  - **S3**: 5GB standard storage, 20,000 GET requests/month.
  - **CloudFront**: 1 TB of data transfer out per month, 10 million HTTP/S requests.
- **Strategy**: Build the Vite/React frontend and the landing page into static assets (`dist` folders) and upload them to separate S3 buckets. CloudFront distributions will serve them over HTTPS with aggressive edge caching.

### 2. Backend (FastAPI / Docker)
- **Service**: Amazon EC2 (t2.micro or t3.micro)
- **Free Tier Allowance**: 750 hours per month (enough to run 24/7). 30 GB of EBS General Purpose (SSD) storage.
- **Strategy**: 
  - Provision an Amazon Linux 2023 or Ubuntu EC2 instance.
  - Install Docker and Docker Compose.
  - Run the existing `backend` service using the provided `docker-compose.yml`.
  - Expose port `8000` via AWS Security Groups, or set up a free tier Application Load Balancer / Nginx reverse proxy on the instance for HTTPS.

### 3. Database
- **Option A (SQLite - Current)**: Hosted directly on the EC2 instance's EBS volume (30GB free). Easiest to set up, but riskier for persistent data.
- **Option B (Amazon RDS - Recommended)**: Provision a `db.t3.micro` or `db.t4g.micro` PostgreSQL or MySQL instance. (Free Tier: 750 hours/month + 20 GB storage). This is highly recommended for production to prevent data loss if the EC2 instance is terminated or replaced.

## Account Distribution Strategy (Using 2 Accounts)

A single AWS account's free tier is sufficient to host this entire project (750 hrs/mo of EC2 + 750 hrs/mo of RDS + generous S3/CloudFront limits). If you wish to utilize two accounts to maximize resources:
- **Account 1 (Production)**: Hosts the live Frontend, Landing Page, Backend EC2, and RDS DB.
- **Account 2 (Staging / CI-CD Runner)**: Hosts an identical replica of the stack for testing changes before they hit production, preventing you from going over the 750-hour limit in Account 1.

## CI/CD Pipeline (GitHub Actions)

Since GitHub Actions is free for public repos (and has a generous free tier for private), it should be used to automate deployments:
1. **Frontend/Landing Page**: On push to `main`, GitHub Actions builds the Vite app and syncs it to the S3 buckets, then invalidates the CloudFront cache.
2. **Backend**: On push to `main`, GitHub Actions SSHs into the EC2 instance, pulls the latest code, and runs `docker compose up -d --build`.
