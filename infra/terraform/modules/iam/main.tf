terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70, < 6.0"
    }
  }
}

variable "name_prefix" {
  description = "Prefix for role names."
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name (the CI deploy role may describe this cluster only)."
  type        = string
}

variable "oidc_provider_arn" {
  description = "EKS IRSA OIDC provider ARN."
  type        = string
}

variable "oidc_provider_url" {
  description = "EKS IRSA OIDC issuer without https://."
  type        = string
}

variable "kubernetes_namespace" {
  description = "Namespace the UrbanFlow workloads run in."
  type        = string
  default     = "urbanflow"
}

variable "backend_service_account" {
  description = "Service account of the API pods."
  type        = string
  default     = "backend"
}

variable "worker_service_account" {
  description = "Service account of the job worker pods."
  type        = string
  default     = "worker"
}

variable "bucket_arns" {
  description = "Run-store buckets keyed by purpose (needs runs and results)."
  type        = map(string)
}

variable "queue_arn" {
  description = "Job queue ARN."
  type        = string
}

variable "dlq_arn" {
  description = "Dead-letter queue ARN."
  type        = string
}

variable "secret_arns" {
  description = "Secrets Manager ARNs the API may read, keyed by short name."
  type        = map(string)
  default     = {}
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the CI roles, as owner/name."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must look like owner/name."
  }
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub Actions OIDC provider. Set false if the account already has one (only one per account is allowed)."
  type        = bool
  default     = true
}

variable "github_environment" {
  description = "GitHub environment whose jobs may assume the deploy role."
  type        = string
  default     = "staging"
}

variable "state_bucket_arn" {
  description = "Terraform state bucket the plan role reads and locks in."
  type        = string
}

variable "ecr_repository_arns" {
  description = "ECR repositories the deploy role may push images to."
  type        = list(string)
  default     = []
}

data "aws_partition" "current" {}

locals {
  oidc_sub_prefix = "system:serviceaccount:${var.kubernetes_namespace}"
  github_issuer   = "token.actions.githubusercontent.com"
  cluster_arn     = "arn:${data.aws_partition.current.partition}:eks:*:*:cluster/${var.cluster_name}"
  object_arns     = [for k in ["runs", "results"] : "${var.bucket_arns[k]}/*"]
  bucket_arns     = [var.bucket_arns["runs"], var.bucket_arns["results"]]
}

# ---- IRSA: pods assume these through their service account ------------------------------------

data "aws_iam_policy_document" "backend_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["${local.oidc_sub_prefix}:${var.backend_service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "worker_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["${local.oidc_sub_prefix}:${var.worker_service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backend" {
  name               = "${var.name_prefix}-backend"
  assume_role_policy = data.aws_iam_policy_document.backend_trust.json
}

resource "aws_iam_role" "worker" {
  name               = "${var.name_prefix}-worker"
  assume_role_policy = data.aws_iam_policy_document.worker_trust.json
}

data "aws_iam_policy_document" "backend" {
  statement {
    sid       = "RunStoreReadWrite"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = local.object_arns
  }

  statement {
    sid       = "RunStoreList"
    actions   = ["s3:ListBucket"]
    resources = local.bucket_arns
  }

  statement {
    sid       = "EnqueueJobs"
    actions   = ["sqs:SendMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
    resources = [var.queue_arn, var.dlq_arn]
  }

  dynamic "statement" {
    for_each = length(var.secret_arns) > 0 ? [1] : []

    content {
      sid       = "ReadAppSecrets"
      actions   = ["secretsmanager:GetSecretValue"]
      resources = values(var.secret_arns)
    }
  }
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid       = "RunStoreWrite"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = local.object_arns
  }

  statement {
    sid       = "RunStoreList"
    actions   = ["s3:ListBucket"]
    resources = local.bucket_arns
  }

  statement {
    sid = "ConsumeJobs"

    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
    ]

    resources = [var.queue_arn]
  }

  statement {
    sid       = "DeadLetterPoisonJobs"
    actions   = ["sqs:SendMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
    resources = [var.dlq_arn]
  }
}

resource "aws_iam_role_policy" "backend" {
  name   = "backend"
  role   = aws_iam_role.backend.id
  policy = data.aws_iam_policy_document.backend.json
}

resource "aws_iam_role_policy" "worker" {
  name   = "worker"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}

# ---- CI: GitHub Actions assumes these through OIDC, no stored keys -----------------------------

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url             = "https://${local.github_issuer}"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

locals {
  github_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${local.github_issuer}"
}

data "aws_caller_identity" "current" {}

# Pull requests may run `terraform plan`: read-only, nothing else.
data "aws_iam_policy_document" "ci_plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_issuer}:sub"
      values   = ["repo:${var.github_repository}:pull_request"]
    }
  }
}

# Only jobs that run in the staging environment (manual dispatch or a release tag) may deploy.
data "aws_iam_policy_document" "ci_deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_issuer}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_issuer}:sub"
      values   = ["repo:${var.github_repository}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "ci_plan" {
  name                 = "${var.name_prefix}-ci-plan"
  assume_role_policy   = data.aws_iam_policy_document.ci_plan_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role" "ci_deploy" {
  name                 = "${var.name_prefix}-ci-deploy"
  assume_role_policy   = data.aws_iam_policy_document.ci_deploy_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "ci_plan_read" {
  role       = aws_iam_role.ci_plan.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/ReadOnlyAccess"
}

data "aws_iam_policy_document" "ci_plan" {
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [var.state_bucket_arn, "${var.state_bucket_arn}/*"]
  }

  statement {
    sid       = "StateLockfile"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.state_bucket_arn}/*.tflock"]
  }
}

resource "aws_iam_role_policy" "ci_plan" {
  name   = "state"
  role   = aws_iam_role.ci_plan.id
  policy = data.aws_iam_policy_document.ci_plan.json
}

data "aws_iam_policy_document" "ci_deploy" {
  statement {
    sid       = "DescribeCluster"
    actions   = ["eks:DescribeCluster"]
    resources = [local.cluster_arn]
  }

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  dynamic "statement" {
    for_each = length(var.ecr_repository_arns) > 0 ? [1] : []

    content {
      sid = "EcrPush"

      actions = [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:CompleteLayerUpload",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:UploadLayerPart",
      ]

      resources = var.ecr_repository_arns
    }
  }
}

resource "aws_iam_role_policy" "ci_deploy" {
  name   = "deploy"
  role   = aws_iam_role.ci_deploy.id
  policy = data.aws_iam_policy_document.ci_deploy.json
}

output "backend_role_arn" {
  description = "IRSA role for the API pods (annotate the backend service account)."
  value       = aws_iam_role.backend.arn
}

output "worker_role_arn" {
  description = "IRSA role for the worker pods (annotate the worker service account)."
  value       = aws_iam_role.worker.arn
}

output "ci_plan_role_arn" {
  description = "Role for terraform plan on pull requests."
  value       = aws_iam_role.ci_plan.arn
}

output "ci_deploy_role_arn" {
  description = "Role for helm deploys from the staging environment."
  value       = aws_iam_role.ci_deploy.arn
}
