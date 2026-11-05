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
  description = "Prefix for bucket names, for example urbanflow-staging. A random-free, account-scoped suffix is added."
  type        = string
}

variable "buckets" {
  description = "Buckets to create, keyed by purpose (runs, results)."
  type        = set(string)
  default     = ["runs", "results"]

  validation {
    condition     = alltrue([for b in var.buckets : can(regex("^[a-z0-9-]{1,20}$", b))])
    error_message = "Bucket purposes must be 1-20 characters: lowercase letters, digits and hyphens."
  }
}

variable "kms_key_arn" {
  description = "Customer-managed KMS key for server-side encryption. Null uses S3-managed keys (SSE-S3), which costs nothing."
  type        = string
  default     = null
}

variable "noncurrent_version_days" {
  description = "Days to keep old object versions before they expire."
  type        = number
  default     = 30

  validation {
    condition     = var.noncurrent_version_days >= 1
    error_message = "noncurrent_version_days must be at least 1."
  }
}

variable "transition_to_ia_days" {
  description = "Days before current objects move to STANDARD_IA (minimum 30 for S3)."
  type        = number
  default     = 30

  validation {
    condition     = var.transition_to_ia_days >= 30
    error_message = "S3 requires at least 30 days before a transition to STANDARD_IA."
  }
}

variable "expire_current_days" {
  description = "Days after which current objects are deleted. 0 keeps them forever."
  type        = number
  default     = 0

  validation {
    condition     = var.expire_current_days == 0 || var.expire_current_days > var.transition_to_ia_days
    error_message = "expire_current_days must be 0 or greater than transition_to_ia_days."
  }
}

variable "force_destroy" {
  description = "Allow terraform destroy to delete non-empty buckets. Keep false outside throwaway environments."
  type        = bool
  default     = false
}

data "aws_caller_identity" "current" {}

locals {
  names = { for b in var.buckets : b => "${var.name_prefix}-${b}-${data.aws_caller_identity.current.account_id}" }
}

resource "aws_s3_bucket" "this" {
  for_each = local.names

  bucket        = each.value
  force_destroy = var.force_destroy
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = aws_s3_bucket.this

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id

  rule {
    bucket_key_enabled = var.kms_key_arn != null

    apply_server_side_encryption_by_default {
      sse_algorithm     = var.kms_key_arn == null ? "AES256" : "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id

  rule {
    id     = "tiering-and-cleanup"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_days
    }

    transition {
      days          = var.transition_to_ia_days
      storage_class = "STANDARD_IA"
    }

    dynamic "expiration" {
      for_each = var.expire_current_days > 0 ? [var.expire_current_days] : []

      content {
        days = expiration.value
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}

data "aws_iam_policy_document" "tls_only" {
  for_each = aws_s3_bucket.this

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]

    resources = [
      each.value.arn,
      "${each.value.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id
  policy = data.aws_iam_policy_document.tls_only[each.key].json

  depends_on = [aws_s3_bucket_public_access_block.this]
}

output "bucket_names" {
  description = "Bucket names keyed by purpose."
  value       = { for k, b in aws_s3_bucket.this : k => b.id }
}

output "bucket_arns" {
  description = "Bucket ARNs keyed by purpose."
  value       = { for k, b in aws_s3_bucket.this : k => b.arn }
}
