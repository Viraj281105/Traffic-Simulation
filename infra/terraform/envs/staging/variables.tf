variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name (mandatory cost tag)."
  type        = string
  default     = "urbanflow"
}

variable "env" {
  description = "Environment name (mandatory cost tag)."
  type        = string
  default     = "staging"
}

variable "owner" {
  description = "Owner of the cost (mandatory cost tag)."
  type        = string
}

variable "tenant" {
  description = "Optional tenant tag for dedicated environments."
  type        = string
  default     = null
}

variable "github_repository" {
  description = "Repository allowed to assume the CI roles, as owner/name."
  type        = string
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub OIDC provider (false if the account already has one)."
  type        = bool
  default     = true
}

variable "state_bucket_name" {
  description = "Name of the pre-existing Terraform state bucket."
  type        = string
}

variable "alert_emails" {
  description = "Addresses for budget alerts."
  type        = list(string)
}

variable "monthly_budget_usd" {
  description = "Monthly cost cap in USD."
  type        = number
}

variable "enable_nat_gateway" {
  description = "Create a NAT gateway (needed for nodes to pull images)."
  type        = bool
  default     = true
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.31"
}

variable "spot_max_size" {
  description = "Maximum spot worker nodes."
  type        = number
  default     = 4
}

variable "deletion_protection" {
  description = "Protect the database from deletion. False by default so staging can be torn down."
  type        = bool
  default     = false
}

variable "force_destroy" {
  description = "Let terraform destroy empty the run buckets and skip the final database snapshot. Staging only."
  type        = bool
  default     = true
}
