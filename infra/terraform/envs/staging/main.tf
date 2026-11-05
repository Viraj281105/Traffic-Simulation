module "tagging" {
  source = "../../modules/tagging"

  project = var.project
  env     = var.env
  owner   = var.owner
  tenant  = var.tenant
}

locals {
  name_prefix  = "${var.project}-${var.env}"
  cluster_name = local.name_prefix
}

module "network" {
  source = "../../modules/network"

  name_prefix        = local.name_prefix
  eks_cluster_name   = local.cluster_name
  enable_nat_gateway = var.enable_nat_gateway
}

module "eks" {
  source = "../../modules/eks"

  cluster_name       = local.cluster_name
  kubernetes_version = var.kubernetes_version
  subnet_ids         = module.network.private_subnet_ids
  spot_max_size      = var.spot_max_size
}

module "storage" {
  source = "../../modules/storage"

  name_prefix   = local.name_prefix
  force_destroy = var.force_destroy
}

module "sqs" {
  source = "../../modules/sqs"

  name_prefix = local.name_prefix
}

module "secrets" {
  source = "../../modules/secrets"

  name_prefix             = "${var.project}/${var.env}"
  recovery_window_in_days = var.force_destroy ? 0 : 7
}

module "database" {
  source = "../../modules/database"

  name_prefix                = local.name_prefix
  vpc_id                     = module.network.vpc_id
  subnet_ids                 = module.network.private_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  deletion_protection        = var.deletion_protection
  skip_final_snapshot        = var.force_destroy
}

module "iam" {
  source = "../../modules/iam"

  name_prefix                 = local.name_prefix
  cluster_name                = local.cluster_name
  oidc_provider_arn           = module.eks.oidc_provider_arn
  oidc_provider_url           = module.eks.oidc_provider_url
  bucket_arns                 = module.storage.bucket_arns
  queue_arn                   = module.sqs.queue_arn
  dlq_arn                     = module.sqs.dlq_arn
  secret_arns                 = module.secrets.secret_arns
  github_repository           = var.github_repository
  create_github_oidc_provider = var.create_github_oidc_provider
  state_bucket_arn            = "arn:aws:s3:::${var.state_bucket_name}"
  ecr_repository_arns         = [for r in aws_ecr_repository.app : r.arn]
}

# Image repositories, named <project>-<env>/backend and /frontend. Nodes pull through the node role.
resource "aws_ecr_repository" "app" {
  for_each = toset(["backend", "frontend"])

  name                 = "${local.name_prefix}/${each.value}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.force_destroy

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  for_each = aws_ecr_repository.app

  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the 30 most recent images"

      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }

      action = { type = "expire" }
    }]
  })
}

module "budgets" {
  source = "../../modules/budgets"

  name_prefix         = local.name_prefix
  monthly_limit_usd   = var.monthly_budget_usd
  notification_emails = var.alert_emails
}

# The CI deploy role may administer the urbanflow namespace only. The namespace itself is created
# once by a cluster admin (README, step 5), so CI never needs cluster-wide rights.
resource "aws_eks_access_entry" "ci_deploy" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.iam.ci_deploy_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "ci_deploy" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.iam.ci_deploy_role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSAdminPolicy"

  access_scope {
    type       = "namespace"
    namespaces = ["urbanflow"]
  }

  depends_on = [aws_eks_access_entry.ci_deploy]
}
