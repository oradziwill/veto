resource "aws_ecs_cluster" "main" {
  name = "${local.name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.name}/backend"
  retention_in_days = var.env == "prod" ? 30 : 7
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${local.name}/frontend"
  retention_in_days = var.env == "prod" ? 30 : 7
}

# --- Backend task definition ---
resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_task_cpu
  memory                   = var.backend_task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = var.backend_image
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "DJANGO_SETTINGS_MODULE", value = "config.settings_production" },
      { name = "ALLOWED_HOSTS", value = "${aws_lb.main.dns_name},localhost,127.0.0.1,*" },
      { name = "CSRF_TRUSTED_ORIGINS", value = "http://${aws_lb.main.dns_name}" },
      { name = "RDS_HOSTNAME", value = aws_db_instance.main.address },
      { name = "RDS_PORT", value = tostring(aws_db_instance.main.port) },
      { name = "RDS_DB_NAME", value = aws_db_instance.main.db_name },
      { name = "RDS_USERNAME", value = aws_db_instance.main.username },
      { name = "REMINDER_EMAIL_PROVIDER", value = var.reminder_email_provider },
      { name = "REMINDER_SMS_PROVIDER", value = var.reminder_sms_provider },
      { name = "REMINDER_SENDGRID_FROM_EMAIL", value = var.reminder_sendgrid_from_email },
      { name = "REMINDER_SENDGRID_FROM_NAME", value = var.reminder_sendgrid_from_name },
      { name = "REMINDER_TWILIO_FROM_NUMBER", value = var.reminder_twilio_from_number },
      { name = "REMINDER_TWILIO_STATUS_CALLBACK_URL", value = var.reminder_twilio_status_callback_url },
      # Disable until HTTPS is configured on the ALB
      { name = "SECURE_SSL_REDIRECT", value = "False" },
    ]

    secrets = concat(
      [
        { name = "SECRET_KEY", valueFrom = aws_secretsmanager_secret.django_secret_key.arn },
        { name = "RDS_PASSWORD", valueFrom = aws_secretsmanager_secret.db_password.arn },
        { name = "CORS_ALLOWED_ORIGINS", valueFrom = aws_secretsmanager_secret.cors_allowed_origins.arn },
        { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_api_key.arn },
      ],
      var.reminder_email_provider == "sendgrid" ? [
        { name = "REMINDER_SENDGRID_API_KEY", valueFrom = aws_secretsmanager_secret.reminder_sendgrid_api_key.arn },
        { name = "REMINDER_SENDGRID_WEBHOOK_SECRET", valueFrom = aws_secretsmanager_secret.reminder_sendgrid_webhook_secret.arn },
      ] : [],
      var.reminder_sms_provider == "twilio" ? [
        { name = "REMINDER_TWILIO_ACCOUNT_SID", valueFrom = aws_secretsmanager_secret.reminder_twilio_account_sid.arn },
        { name = "REMINDER_TWILIO_AUTH_TOKEN", valueFrom = aws_secretsmanager_secret.reminder_twilio_auth_token.arn },
        { name = "REMINDER_TWILIO_WEBHOOK_SECRET", valueFrom = aws_secretsmanager_secret.reminder_twilio_webhook_secret.arn },
      ] : [],
      length(trimspace(var.reminder_webhook_token)) > 0 ? [
        { name = "REMINDER_WEBHOOK_TOKEN", valueFrom = aws_secretsmanager_secret.reminder_webhook_token.arn },
      ] : [],
    )

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.backend.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# --- Frontend task definition ---
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${local.name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.frontend_task_cpu
  memory                   = var.frontend_task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = var.frontend_image
    essential = true

    portMappings = [{
      containerPort = 80
      protocol      = "tcp"
    }]

    environment = [
      # nginx proxies /api/ to the backend service via service discovery
      { name = "BACKEND_URL", value = "http://backend.${aws_service_discovery_private_dns_namespace.main.name}:8000" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# --- ECS Services ---
resource "aws_ecs_service" "backend" {
  name            = "${local.name}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  service_registries {
    registry_arn = aws_service_discovery_service.backend.arn
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  enable_execute_command = true

  depends_on = [aws_lb_listener_rule.api]

  lifecycle {
    # image tag is updated by CI/CD, not Terraform
    ignore_changes = [task_definition]
  }
}

resource "aws_ecs_service" "frontend" {
  name            = "${local.name}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  enable_execute_command = true

  depends_on = [aws_lb_listener.http]

  lifecycle {
    ignore_changes = [task_definition]
  }
}
