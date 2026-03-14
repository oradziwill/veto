resource "aws_secretsmanager_secret" "django_secret_key" {
  name                    = "${local.name}/django-secret-key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "django_secret_key" {
  secret_id     = aws_secretsmanager_secret.django_secret_key.id
  secret_string = var.django_secret_key

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${local.name}/db-password"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "cors_allowed_origins" {
  name                    = "${local.name}/cors-allowed-origins"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "cors_allowed_origins" {
  secret_id     = aws_secretsmanager_secret.cors_allowed_origins.id
  secret_string = var.cors_allowed_origins

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "${local.name}/openai-api-key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  count = length(trimspace(var.openai_api_key)) > 0 ? 1 : 0

  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key

  lifecycle {
    ignore_changes = [secret_string]
  }
}
