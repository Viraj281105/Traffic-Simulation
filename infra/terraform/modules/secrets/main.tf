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
  description = "Path prefix for secret names, for example urbanflow/staging."
  type        = string
}

variable "secret_names" {
  description = "Secrets to create (empty containers: no value is ever set here)."
  type        = set(string)
  default     = ["api-key", "metrics-token", "oidc-client-secret"]

  validation {
    condition     = alltrue([for s in var.secret_names : can(regex("^[a-z0-9][a-z0-9/_-]{0,63}$", s))])
    error_message = "Secret names must be lowercase letters, digits, '/', '_' or '-', up to 64 characters."
  }
}

variable "kms_key_arn" {
  description = "Customer-managed KMS key. Null uses the AWS-managed aws/secretsmanager key."
  type        = string
  default     = null
}

variable "recovery_window_in_days" {
  description = "Days a deleted secret can be recovered. 0 deletes at once (throwaway environments only)."
  type        = number
  default     = 7

  validation {
    condition     = var.recovery_window_in_days == 0 || (var.recovery_window_in_days >= 7 && var.recovery_window_in_days <= 30)
    error_message = "recovery_window_in_days must be 0 or between 7 and 30."
  }
}

# Only the container is managed. Values are put with `aws secretsmanager put-secret-value` out of band,
# so no secret ever lands in the repository or in Terraform state.
resource "aws_secretsmanager_secret" "this" {
  for_each = var.secret_names

  name                    = "${var.name_prefix}/${each.value}"
  description             = "UrbanFlow ${each.value}. Value is set out of band."
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_in_days
}

output "secret_arns" {
  description = "Secret ARNs keyed by short name."
  value       = { for k, s in aws_secretsmanager_secret.this : k => s.arn }
}
