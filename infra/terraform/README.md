# UrbanFlow on AWS: Terraform (package 2E)

Status: **WRITTEN, not applied, not validated.** `terraform` was not installed where this was written, so
`terraform fmt -check` and `terraform validate` have not been run. Run both first (see "Before you apply").
Nothing here has touched an AWS account.

## Layout

```
infra/terraform/
  modules/
    tagging/    mandatory cost tags (project, env, owner; tenant optional) -> provider default_tags
    network/    VPC, public and private subnets, optional NAT, S3 gateway endpoint
    storage/    S3 buckets runs + results: versioning, encryption, public-access block, TLS-only, lifecycle
    database/   RDS PostgreSQL: subnet group, security group, private, encrypted, password in Secrets Manager
    secrets/    Secrets Manager entries (containers only, no values)
    eks/        cluster, on-demand "system" node group, tainted spot "spot-batch" node group, IRSA provider
    sqs/        job queue, dead-letter queue, redrive, DLQ alarm
    iam/        IRSA roles (backend, worker) and GitHub OIDC roles (ci-plan, ci-deploy)
    budgets/    monthly AWS Budget with actual and forecast email alerts
  envs/staging/ the staging stack that wires the modules together
```

Each module is one `main.tf` holding its `terraform` block, variables, resources and outputs.

## Cost tags

Every resource gets `project`, `env`, `owner` and `managed-by` through the provider's `default_tags`
(`envs/staging/versions.tf`, fed by `modules/tagging`). `tenant` is added only when the variable is set.
Missing or malformed values fail at plan time (variable validation). After the first apply, activate
`project`, `env`, `owner` (and `tenant`) under Billing > Cost allocation tags; tags only appear in Cost
Explorer from the day they are activated. The job worker tags each run the same way (`backend/src/jobs/cost_tags.py`).

## Before you apply

1. Install Terraform 1.10 or newer (the S3 backend uses native lock files) and the AWS CLI.
2. `terraform fmt -check -recursive infra/terraform` and, in `envs/staging`, `terraform init -backend=false && terraform validate`.
3. Use a **dedicated AWS account or a dedicated billing alert**. The monthly budget alerts; it does not stop spending.

## Plan and apply order

A single `terraform apply` of `envs/staging` orders everything itself. The manual steps around it:

1. **State bucket (once, by hand).** Create a private, versioned, encrypted S3 bucket for state. Put its name in
   `staging.tfvars` (`state_bucket_name`) and in `backend.hcl`.
2. `cp backend.hcl.example backend.hcl` and `cp staging.tfvars.example staging.tfvars`; edit both. Both are git-ignored.
3. `terraform init -backend-config=backend.hcl`
4. `terraform plan -var-file=staging.tfvars -out=staging.tfplan`, read it, then `terraform apply staging.tfplan`.
   Internally the order is: tagging, network, eks, storage, sqs, secrets, database, iam, budgets, CI access entry.
   The EKS cluster takes about 12 minutes.
5. **Bootstrap the cluster (once).** `aws eks update-kubeconfig --name urbanflow-staging`, then
   `kubectl create namespace urbanflow`. The CI role is namespace-scoped and cannot create it.
6. **Set secret values (out of band, never in Terraform).**
   `aws secretsmanager put-secret-value --secret-id urbanflow/staging/api-key --secret-string "..."`, likewise
   `metrics-token` and `oidc-client-secret`. The database password is generated and held by RDS
   (output `database_master_secret_arn`).
7. **Repository variables** (GitHub > Settings > Variables, not secrets, these are not sensitive):
   `AWS_STAGING_ENABLED=true`, `AWS_REGION`, `AWS_PLAN_ROLE_ARN`, `AWS_DEPLOY_ROLE_ARN`, `EKS_CLUSTER_NAME`,
   `TF_STATE_BUCKET`, and the staging `tfvars` values the plan job needs (see `.github/workflows/aws-staging.yml`).
8. Install the cluster add-ons the worker chart relies on, once: KEDA and the cluster autoscaler (see
   `deploy/autoscaling/README.md`), then deploy the chart with the worker enabled.

## Teardown

1. `helm uninstall urbanflow -n urbanflow` (removes load balancers the cluster created; Terraform cannot see them).
2. `terraform destroy -var-file=staging.tfvars`. With the staging defaults (`force_destroy=true`,
   `deletion_protection=false`) buckets are emptied and the database is dropped without a final snapshot.
   For anything you want to keep, set those to false/true respectively **before** the first apply.
3. Delete the state bucket by hand. Secrets are deleted immediately under the staging defaults.
4. Check the billing console the next day: NAT gateways, EBS volumes and load balancers are the usual leftovers.

## Security notes

- The database has no public endpoint and no ingress except from the EKS cluster security group.
- Roles are least-privilege: the backend can enqueue and read/write the run store and read the app secrets; the worker can
  consume the job queue, dead-letter to the DLQ and read/write the run store (no delete). CI plan is read-only
  (`ReadOnlyAccess` plus the state bucket). CI deploy can describe the cluster, log in to ECR, and administer only the
  `urbanflow` namespace. CI cannot apply Terraform: apply stays a human step.
- The EKS public endpoint defaults to `0.0.0.0/0` (still IAM-authenticated) so GitHub-hosted runners can deploy.
  Narrow `public_access_cidrs` in `modules/eks` if you use self-hosted runners.
- Kubernetes secrets are encrypted with a dedicated KMS key.
- The OIDC thumbprints in the `eks` and `iam` modules are the well-known root CA values; AWS no longer validates
  them for these issuers.

## Cost estimate (approximate)

Prices are rough **list prices for us-east-1 at the time of writing, in USD**, taken from memory of public
pricing pages and **not checked against the live price list**. Treat them as order of magnitude and re-check
with the AWS Pricing Calculator before applying. Spot prices vary by the hour.

| Item | Assumption | Approx. USD per month |
|---|---|---|
| EKS control plane | 1 cluster, about 0.10 per hour | 73 |
| NAT gateway | 1 shared, about 0.045 per hour, plus 0.045 per GB processed | 33 + data |
| System nodes | 2 x t3.medium on-demand, about 0.042 per hour each | 61 |
| Node root volumes | 2 x 20 GiB gp3 | 3 |
| RDS PostgreSQL | db.t4g.micro single-AZ, 20 GiB gp3 | 15 |
| Spot worker nodes | c5.xlarge-class at roughly 30 to 40 percent of on-demand (0.17 per hour); **zero when the queue is empty** | about 0.06 per node-hour; 100 node-hours is about 6 |
| S3 | a few GiB of runs and results | under 1 |
| SQS | well inside the free tier (1 million requests) | 0 |
| Secrets Manager | 3 app secrets + 1 RDS secret, about 0.40 each | 1.6 |
| KMS | 1 key for EKS secrets | 1 |
| CloudWatch logs and alarm | control plane logs, 14 days | 2 to 5 |
| **Idle floor** | everything above, no batch work | **about 190** |

Levers: `enable_nat_gateway=false` saves about 33 but needs VPC endpoints for image pulls (not provided);
one system node instead of two saves about 30; stopping the RDS instance when idle saves about 12.
The example `monthly_budget_usd` of 250 sits above the idle floor on purpose; a budget below it would alarm every month.
The **budget does not cap spending**: AWS Budgets only alerts. The cap that stops new jobs is the application's (F17),
built on the compute-time records in `backend/src/jobs/cost_tags.py` and the later `src/costing` package.
