# One Fargate task runs both containers. They share the task's network, so the frontend's
# Backend-for-Frontend reaches the API at localhost:8000 and the API is never exposed.

resource "aws_ecs_cluster" "main" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = "disabled" # adds cost; the log group and alarms below cover the demo
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.name}"
  retention_in_days = 14
}

locals {
  registry = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
  log_options = {
    "awslogs-group"         = aws_cloudwatch_log_group.app.name
    "awslogs-region"        = var.region
    "awslogs-stream-prefix" = "app"
  }
  backend_secrets = concat(
    [
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
      { name = "JWT_SECRET", valueFrom = aws_secretsmanager_secret.jwt.arn },
    ],
    [for arn in aws_secretsmanager_secret.gemini[*].arn : { name = "GEMINI_API_KEY", valueFrom = arn }],
  )
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64" # images are built on an Apple-silicon Mac; Graviton is also cheaper
  }

  container_definitions = jsonencode([
    {
      name         = "backend"
      image        = "${local.registry}/${var.name}-backend:${var.image_tag}"
      essential    = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "ENVIRONMENT", value = "production" },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "LLM_PROVIDER", value = var.llm_provider },
        { name = "BEDROCK_REGION", value = var.region },
        { name = "BEDROCK_MODEL", value = var.bedrock_model },
      ]
      secrets = local.backend_secrets
      healthCheck = {
        command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
        interval    = 15
        timeout     = 3
        retries     = 3
        startPeriod = 60
      }
      logConfiguration = { logDriver = "awslogs", options = merge(local.log_options, { "awslogs-stream-prefix" = "backend" }) }
    },
    {
      name         = "frontend"
      image        = "${local.registry}/${var.name}-frontend:${var.image_tag}"
      essential    = true
      portMappings = [{ containerPort = 3000, protocol = "tcp" }]
      environment = [
        { name = "BACKEND_URL", value = "http://127.0.0.1:8000" },
      ]
      dependsOn        = [{ containerName = "backend", condition = "HEALTHY" }]
      logConfiguration = { logDriver = "awslogs", options = merge(local.log_options, { "awslogs-stream-prefix" = "frontend" }) }
    },
  ])
}

resource "aws_ecs_service" "app" {
  name            = var.name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 120

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 3000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.http]
}
