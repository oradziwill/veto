output "alb_dns_name" {
  description = "ALB DNS — open this in your browser"
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecr_backend_url" {
  description = "ECR repository URL for the backend image"
  value = coalesce(
    try(aws_ecr_repository.backend[0].repository_url, null),
    "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com/${var.app_name}-backend",
  )
}

output "ecr_frontend_url" {
  description = "ECR repository URL for the frontend image"
  value = coalesce(
    try(aws_ecr_repository.frontend[0].repository_url, null),
    "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com/${var.app_name}-frontend",
  )
}

output "rds_hostname" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.address
  sensitive   = true
}

output "ecs_cluster_name" {
  description = "ECS cluster name (used in CI/CD)"
  value       = aws_ecs_cluster.main.name
}

output "ecs_backend_service_name" {
  description = "ECS backend service name (used in CI/CD)"
  value       = aws_ecs_service.backend.name
}

output "ecs_frontend_service_name" {
  description = "ECS frontend service name (used in CI/CD)"
  value       = aws_ecs_service.frontend.name
}
