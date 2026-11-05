terraform {
  required_version = ">= 1.10.0"
}

variable "project" {
  description = "Project name. Mandatory cost tag `project`."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.project))
    error_message = "project must be 2-31 characters: lowercase letters, digits and hyphens, starting with a letter."
  }
}

variable "env" {
  description = "Environment. Mandatory cost tag `env`."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of dev, staging, prod."
  }
}

variable "owner" {
  description = "Team or person accountable for the cost. Mandatory cost tag `owner`."
  type        = string

  validation {
    condition     = length(trimspace(var.owner)) > 0 && length(var.owner) <= 128
    error_message = "owner must be a non-empty string of at most 128 characters."
  }
}

variable "tenant" {
  description = "Optional tenant the resources are dedicated to. Omit for shared infrastructure."
  type        = string
  default     = null

  validation {
    condition     = var.tenant == null ? true : can(regex("^[a-z0-9][a-z0-9_-]{0,62}$", var.tenant))
    error_message = "tenant must be 1-63 characters: lowercase letters, digits, hyphens and underscores."
  }
}

variable "extra_tags" {
  description = "Additional tags. They can never override the mandatory ones."
  type        = map(string)
  default     = {}

  validation {
    condition     = alltrue([for k in keys(var.extra_tags) : !startswith(lower(k), "aws:")])
    error_message = "Tag keys must not start with the reserved prefix aws:."
  }
}

locals {
  mandatory = {
    project    = var.project
    env        = var.env
    owner      = var.owner
    managed-by = "terraform"
  }

  tenant_tag = var.tenant == null ? {} : { tenant = var.tenant }
}

output "tags" {
  description = "Tag map for the provider default_tags block."
  value       = merge(var.extra_tags, local.tenant_tag, local.mandatory)
}

output "cost_allocation_tag_keys" {
  description = "Tag keys to activate as cost allocation tags in the billing console."
  value       = concat(["project", "env", "owner"], var.tenant == null ? [] : ["tenant"])
}
