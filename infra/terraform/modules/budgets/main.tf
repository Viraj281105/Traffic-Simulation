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
  description = "Prefix for the budget name."
  type        = string
}

variable "monthly_limit_usd" {
  description = "Monthly cost cap in USD. There is deliberately no default: choose it."
  type        = number

  validation {
    condition     = var.monthly_limit_usd > 0 && var.monthly_limit_usd <= 100000
    error_message = "monthly_limit_usd must be greater than 0 and at most 100000."
  }
}

variable "actual_thresholds_percent" {
  description = "Percentages of the limit at which ACTUAL spend triggers an email."
  type        = list(number)
  default     = [50, 80, 100]

  validation {
    condition     = alltrue([for t in var.actual_thresholds_percent : t > 0 && t <= 200])
    error_message = "Thresholds must be between 1 and 200 percent."
  }
}

variable "forecast_threshold_percent" {
  description = "Percentage of the limit at which FORECASTED spend triggers an email."
  type        = number
  default     = 100
}

variable "notification_emails" {
  description = "Addresses that receive budget alerts."
  type        = list(string)

  validation {
    condition     = length(var.notification_emails) > 0 && alltrue([for e in var.notification_emails : can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", e))])
    error_message = "Give at least one valid email address."
  }
}

variable "filter_by_project_tag" {
  description = "Limit the budget to resources tagged project=<project_tag_value>. Needs the project tag activated as a cost allocation tag; leave false for a dedicated account."
  type        = bool
  default     = false
}

variable "project_tag_value" {
  description = "Value of the project tag to filter on."
  type        = string
  default     = "urbanflow"
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "cost_filter" {
    for_each = var.filter_by_project_tag ? [1] : []

    content {
      name   = "TagKeyValue"
      values = [format("user:project$%s", var.project_tag_value)]
    }
  }

  dynamic "notification" {
    for_each = toset([for t in var.actual_thresholds_percent : tostring(t)])

    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = tonumber(notification.value)
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = var.notification_emails
    }
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = var.forecast_threshold_percent
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.notification_emails
  }
}

output "budget_name" {
  description = "Budget name."
  value       = aws_budgets_budget.monthly.name
}
