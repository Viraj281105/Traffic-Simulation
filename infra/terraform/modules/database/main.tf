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
  description = "Prefix for resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC the database lives in."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet ids for the DB subnet group (at least two zones)."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "RDS needs subnets in at least two availability zones."
  }
}

variable "allowed_security_group_ids" {
  description = "Security groups (for example the EKS node group) allowed to connect on 5432. The database has no other ingress and is never publicly accessible."
  type        = list(string)
  default     = []
}

variable "engine_version" {
  description = "PostgreSQL major version; RDS picks the latest minor."
  type        = string
  default     = "16"
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  description = "Initial storage in GiB."
  type        = number
  default     = 20

  validation {
    condition     = var.allocated_storage_gb >= 20 && var.allocated_storage_gb <= 1000
    error_message = "allocated_storage_gb must be between 20 and 1000."
  }
}

variable "max_allocated_storage_gb" {
  description = "Storage autoscaling ceiling in GiB (0 disables autoscaling)."
  type        = number
  default     = 100
}

variable "database_name" {
  description = "Initial database name."
  type        = string
  default     = "urbanflow"
}

variable "master_username" {
  description = "Master user name. The password is generated and kept in Secrets Manager by RDS; it never enters Terraform state."
  type        = string
  default     = "urbanflow_admin"
}

variable "multi_az" {
  description = "Standby in a second zone (doubles the instance cost)."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Automated backup retention in days."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 1 and 35."
  }
}

variable "deletion_protection" {
  description = "Block deletion of the instance. Turn off deliberately before teardown."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip the final snapshot on destroy. Only for throwaway environments."
  type        = bool
  default     = false
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "db" {
  name        = "${var.name_prefix}-db"
  description = "PostgreSQL access for UrbanFlow workloads"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name_prefix}-db" }
}

resource "aws_vpc_security_group_ingress_rule" "from_allowed" {
  for_each = toset(var.allowed_security_group_ids)

  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL from an allowed workload security group"
}

resource "aws_db_instance" "this" {
  identifier = "${var.name_prefix}-pg"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.max_allocated_storage_gb > 0 ? var.max_allocated_storage_gb : null
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name                     = var.database_name
  username                    = var.master_username
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = var.multi_az

  backup_retention_period    = var.backup_retention_days
  deletion_protection        = var.deletion_protection
  skip_final_snapshot        = var.skip_final_snapshot
  final_snapshot_identifier  = var.skip_final_snapshot ? null : "${var.name_prefix}-pg-final"
  copy_tags_to_snapshot      = true
  auto_minor_version_upgrade = true
  apply_immediately          = false
}

output "endpoint" {
  description = "Database host and port."
  value       = aws_db_instance.this.endpoint
}

output "security_group_id" {
  description = "Database security group id."
  value       = aws_security_group.db.id
}

output "master_secret_arn" {
  description = "ARN of the Secrets Manager secret RDS keeps the master password in."
  value       = try(aws_db_instance.this.master_user_secret[0].secret_arn, null)
}
