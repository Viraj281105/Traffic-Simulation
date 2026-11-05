output "cluster_name" {
  description = "EKS cluster name (aws eks update-kubeconfig --name <this>)."
  value       = module.eks.cluster_name
}

output "jobs_queue_url" {
  description = "JOBS_QUEUE_URL for the worker chart."
  value       = module.sqs.queue_url
}

output "jobs_dlq_url" {
  description = "JOBS_DLQ_URL for the worker chart."
  value       = module.sqs.dlq_url
}

output "runs_bucket" {
  description = "RUNSTORE_BUCKET for the backend and worker."
  value       = module.storage.bucket_names["runs"]
}

output "results_bucket" {
  description = "Results bucket."
  value       = module.storage.bucket_names["results"]
}

output "database_endpoint" {
  description = "RDS endpoint."
  value       = module.database.endpoint
}

output "database_master_secret_arn" {
  description = "Secrets Manager ARN of the generated database password."
  value       = module.database.master_secret_arn
}

output "backend_role_arn" {
  description = "IRSA role ARN for the backend service account."
  value       = module.iam.backend_role_arn
}

output "worker_role_arn" {
  description = "IRSA role ARN for the worker service account."
  value       = module.iam.worker_role_arn
}

output "ci_plan_role_arn" {
  description = "Set as repository variable AWS_PLAN_ROLE_ARN."
  value       = module.iam.ci_plan_role_arn
}

output "ci_deploy_role_arn" {
  description = "Set as repository variable AWS_DEPLOY_ROLE_ARN."
  value       = module.iam.ci_deploy_role_arn
}

output "cost_allocation_tag_keys" {
  description = "Activate these in Billing > Cost allocation tags."
  value       = module.tagging.cost_allocation_tag_keys
}

output "ecr_repository_urls" {
  description = "Image repositories keyed by service (ECR_REGISTRY is the host part)."
  value       = { for k, r in aws_ecr_repository.app : k => r.repository_url }
}
