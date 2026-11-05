terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70, < 6.0"
    }
  }
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes minor version. Check the EKS supported-version calendar before applying."
  type        = string
  default     = "1.31"

  validation {
    condition     = can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "kubernetes_version must look like 1.31."
  }
}

variable "subnet_ids" {
  description = "Private subnet ids for the control plane network interfaces and the nodes."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "EKS needs subnets in at least two availability zones."
  }
}

variable "endpoint_public_access" {
  description = "Expose the API server publicly (still IAM-authenticated). Needed for GitHub-hosted runners to deploy."
  type        = bool
  default     = true
}

variable "public_access_cidrs" {
  description = "CIDRs allowed to reach the public API endpoint. Tighten this when you can."
  type        = list(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition     = length(var.public_access_cidrs) > 0 && alltrue([for c in var.public_access_cidrs : can(cidrhost(c, 0))])
    error_message = "public_access_cidrs must be a non-empty list of valid CIDR blocks."
  }
}

variable "log_retention_days" {
  description = "Retention of control plane logs in CloudWatch."
  type        = number
  default     = 14
}

variable "system_instance_types" {
  description = "Instance types of the on-demand system node group (API, frontend, controllers)."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "system_min_size" {
  description = "Minimum nodes in the system group."
  type        = number
  default     = 1
}

variable "system_desired_size" {
  description = "Initial desired nodes in the system group."
  type        = number
  default     = 2
}

variable "system_max_size" {
  description = "Maximum nodes in the system group."
  type        = number
  default     = 3

  validation {
    condition     = var.system_max_size >= 1
    error_message = "system_max_size must be at least 1."
  }
}

variable "spot_instance_types" {
  description = "Several similar instance types, so spot capacity can be found in more pools."
  type        = list(string)
  default     = ["c5.xlarge", "c5a.xlarge", "c6i.xlarge", "m5.xlarge"]

  validation {
    condition     = length(var.spot_instance_types) >= 2
    error_message = "Give at least two instance types for the spot group (diversification)."
  }
}

variable "spot_max_size" {
  description = "Maximum spot nodes: the hard ceiling on batch compute."
  type        = number
  default     = 4

  validation {
    condition     = var.spot_max_size >= 0 && var.spot_max_size <= 50
    error_message = "spot_max_size must be between 0 and 50."
  }
}

data "aws_partition" "current" {}

# ---- Secrets encryption ------------------------------------------------------------------------

resource "aws_kms_key" "cluster" {
  description             = "EKS secrets encryption for ${var.cluster_name}"
  enable_key_rotation     = true
  deletion_window_in_days = 7
}

resource "aws_kms_alias" "cluster" {
  name          = "alias/${var.cluster_name}-eks"
  target_key_id = aws_kms_key.cluster.key_id
}

# ---- Control plane -----------------------------------------------------------------------------

data "aws_iam_policy_document" "cluster_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster" {
  name               = "${var.cluster_name}-cluster"
  assume_role_policy = data.aws_iam_policy_document.cluster_trust.json
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = var.log_retention_days
}

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  enabled_cluster_log_types = ["api", "audit", "authenticator"]

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = var.endpoint_public_access
    public_access_cidrs     = var.public_access_cidrs
  }

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }

  encryption_config {
    resources = ["secrets"]

    provider {
      key_arn = aws_kms_key.cluster.arn
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.cluster,
    aws_cloudwatch_log_group.cluster,
  ]
}

# IAM roles for service accounts (IRSA): the iam module builds trust policies from this provider.
resource "aws_iam_openid_connect_provider" "cluster" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["9e99a48a9960b14926bb7f3b02e22da2b0ab7280"]
}

# ---- Nodes -------------------------------------------------------------------------------------

data "aws_iam_policy_document" "node_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "${var.cluster_name}-node"
  assume_role_policy = data.aws_iam_policy_document.node_trust.json
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "AmazonEKSWorkerNodePolicy",
    "AmazonEKS_CNI_Policy",
    "AmazonEC2ContainerRegistryReadOnly",
  ])

  role       = aws_iam_role.node.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/${each.value}"
}

# On-demand nodes for the always-on services.
resource "aws_eks_node_group" "system" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "system"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  capacity_type   = "ON_DEMAND"
  instance_types  = var.system_instance_types
  ami_type        = "AL2023_x86_64_STANDARD"

  labels = {
    workload = "system"
  }

  scaling_config {
    min_size     = var.system_min_size
    desired_size = var.system_desired_size
    max_size     = var.system_max_size
  }

  update_config {
    max_unavailable = 1
  }

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  depends_on = [aws_iam_role_policy_attachment.node]
}

# Spot nodes for batch simulation workers. Tainted, so only pods that tolerate spot land here;
# they scale to zero when the job queue is empty.
resource "aws_eks_node_group" "spot" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "spot-batch"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  capacity_type   = "SPOT"
  instance_types  = var.spot_instance_types
  ami_type        = "AL2023_x86_64_STANDARD"

  labels = {
    workload       = "batch"
    node-lifecycle = "spot"
  }

  taint {
    key    = "spot"
    value  = "true"
    effect = "NO_SCHEDULE"
  }

  scaling_config {
    min_size     = 0
    desired_size = 0
    max_size     = var.spot_max_size
  }

  update_config {
    max_unavailable = 1
  }

  # Tags the cluster autoscaler reads to discover the group and to scale it up from zero.
  tags = {
    "k8s.io/cluster-autoscaler/enabled"                      = "true"
    "k8s.io/cluster-autoscaler/${var.cluster_name}"          = "owned"
    "k8s.io/cluster-autoscaler/node-template/label/workload" = "batch"
    "k8s.io/cluster-autoscaler/node-template/taint/spot"     = "true:NoSchedule"
  }

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  depends_on = [aws_iam_role_policy_attachment.node]
}

output "cluster_name" {
  description = "Cluster name."
  value       = aws_eks_cluster.this.name
}

output "cluster_arn" {
  description = "Cluster ARN."
  value       = aws_eks_cluster.this.arn
}

output "cluster_endpoint" {
  description = "API server endpoint."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_security_group_id" {
  description = "Security group EKS attaches to the managed nodes (allow it on the database)."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "oidc_provider_arn" {
  description = "IRSA OIDC provider ARN."
  value       = aws_iam_openid_connect_provider.cluster.arn
}

output "oidc_provider_url" {
  description = "IRSA OIDC issuer URL without the scheme."
  value       = replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")
}

output "node_role_arn" {
  description = "Node IAM role ARN."
  value       = aws_iam_role.node.arn
}
