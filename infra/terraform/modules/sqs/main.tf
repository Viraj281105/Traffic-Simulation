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
  description = "Prefix for queue names."
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "How long a received job stays hidden. Must exceed the longest job; the worker also extends it per message."
  type        = number
  default     = 900

  validation {
    condition     = var.visibility_timeout_seconds >= 30 && var.visibility_timeout_seconds <= 43200
    error_message = "visibility_timeout_seconds must be between 30 and 43200 (12 hours)."
  }
}

variable "max_receive_count" {
  description = "Deliveries before a message moves to the dead-letter queue (the redrive policy)."
  type        = number
  default     = 3

  validation {
    condition     = var.max_receive_count >= 1 && var.max_receive_count <= 10
    error_message = "max_receive_count must be between 1 and 10."
  }
}

variable "message_retention_seconds" {
  description = "How long an unprocessed job waits in the main queue."
  type        = number
  default     = 345600
}

variable "dlq_retention_seconds" {
  description = "How long a dead-lettered job is kept for inspection (maximum 14 days)."
  type        = number
  default     = 1209600

  validation {
    condition     = var.dlq_retention_seconds <= 1209600
    error_message = "SQS keeps messages for at most 1209600 seconds (14 days)."
  }
}

variable "alarm_actions" {
  description = "ARNs (for example an SNS topic) notified when the dead-letter queue is not empty."
  type        = list(string)
  default     = []
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name_prefix}-jobs-dlq"
  message_retention_seconds = var.dlq_retention_seconds
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${var.name_prefix}-jobs"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.jobs.arn]
  })
}

resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name          = "${var.name_prefix}-jobs-dlq-not-empty"
  alarm_description   = "A job exhausted its retries and sits in the dead-letter queue."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  period              = 300
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.dlq.name
  }
}

output "queue_url" {
  description = "Job queue URL (JOBS_QUEUE_URL)."
  value       = aws_sqs_queue.jobs.id
}

output "queue_arn" {
  description = "Job queue ARN."
  value       = aws_sqs_queue.jobs.arn
}

output "queue_name" {
  description = "Job queue name (KEDA and alarms)."
  value       = aws_sqs_queue.jobs.name
}

output "dlq_url" {
  description = "Dead-letter queue URL (JOBS_DLQ_URL)."
  value       = aws_sqs_queue.dlq.id
}

output "dlq_arn" {
  description = "Dead-letter queue ARN."
  value       = aws_sqs_queue.dlq.arn
}
