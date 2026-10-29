# The task reads these at start; they never appear in the task definition.
# recovery_window_in_days = 0 lets a destroy and a later apply reuse the names at once.

resource "random_password" "jwt" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.name}/database-url"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql+psycopg://${aws_db_instance.main.username}:${random_password.db.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${aws_db_instance.main.db_name}?sslmode=require"
}

resource "aws_secretsmanager_secret" "jwt" {
  name                    = "${var.name}/jwt-secret"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "jwt" {
  secret_id     = aws_secretsmanager_secret.jwt.id
  secret_string = random_password.jwt.result
}

resource "aws_secretsmanager_secret" "gemini" {
  count                   = var.llm_provider == "gemini" ? 1 : 0
  name                    = "${var.name}/gemini-api-key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "gemini" {
  count         = var.llm_provider == "gemini" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.gemini[0].id
  secret_string = var.gemini_api_key
}

locals {
  secret_arns = concat(
    [aws_secretsmanager_secret.database_url.arn, aws_secretsmanager_secret.jwt.arn],
    aws_secretsmanager_secret.gemini[*].arn,
  )
}
