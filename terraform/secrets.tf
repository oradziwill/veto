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

# ---------------------------------------------------------------------------
# All remaining app secrets consolidated into a single JSON secret.
# ECS extracts individual keys via the ARN:json-key:: syntax.
#
# To update a value after initial creation, edit the secret directly in the
# AWS console or CLI:
#   aws secretsmanager put-secret-value \
#     --secret-id <name> \
#     --secret-string '{"CORS_ALLOWED_ORIGINS":"...","OPENAI_API_KEY":"...",...}'
# ---------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${local.name}/app-secrets"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id

  secret_string = jsonencode({
    CORS_ALLOWED_ORIGINS             = var.cors_allowed_origins
    OPENAI_API_KEY                   = var.openai_api_key
    REMINDER_SENDGRID_API_KEY        = var.reminder_sendgrid_api_key
    REMINDER_SENDGRID_WEBHOOK_SECRET = var.reminder_sendgrid_webhook_secret
    REMINDER_TWILIO_ACCOUNT_SID      = var.reminder_twilio_account_sid
    REMINDER_TWILIO_AUTH_TOKEN       = var.reminder_twilio_auth_token
    REMINDER_TWILIO_WEBHOOK_SECRET   = var.reminder_twilio_webhook_secret
    REMINDER_WEBHOOK_TOKEN           = var.reminder_webhook_token
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
