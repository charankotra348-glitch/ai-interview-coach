output "url" {
  description = "The app, over HTTPS."
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "ecr_backend" {
  value = aws_ecr_repository.app["backend"].repository_url
}

output "ecr_frontend" {
  value = aws_ecr_repository.app["frontend"].repository_url
}

output "cluster" {
  value = aws_ecs_cluster.main.name
}

output "service" {
  value = aws_ecs_service.app.name
}

output "log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "region" {
  value = var.region
}
