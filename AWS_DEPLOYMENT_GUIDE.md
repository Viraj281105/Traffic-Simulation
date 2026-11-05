# AWS Deployment Guide — moved

The deployment documentation now lives in `docs/deployment/`:

| Document | Purpose |
| --- | --- |
| [Deployment & operations](docs/deployment/README.md) | Multi-tier architecture, environment, verification, operations, troubleshooting |
| [AWS EC2 deployment runbook](docs/deployment/AWS_FREE_TIER_DEPLOYMENT.md) | Step-by-step: single EC2 instance, swap, Docker, deploy, backups, updates |
| [AWS Terraform Staging Stack](infra/terraform/README.md) | Production IaC: multi-AZ VPC, EKS cluster, RDS PostgreSQL, encrypted S3, SQS |
| [Local Kubernetes via Kind & Helm](deploy/README.md) | Local Kubernetes deployment and umbrella Helm chart |
| [Production CI/CD setup](docs/deployment/production-cicd-setup.md) | Automated GitHub Actions deployment workflows |

This file is kept so existing links keep working.
