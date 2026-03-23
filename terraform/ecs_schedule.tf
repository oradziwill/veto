#
# Dev-only: scale ECS services and stop RDS outside working hours to save cost.
#
# Schedule (Europe/Warsaw timezone):
#   Weekdays  Mon–Fri  18:00 → start,  22:00 → stop
#   Weekends  Sat–Sun  14:00 → start,  20:00 → stop
#
# RDS starts 5 min before ECS (so DB is ready) and stops 5 min after ECS
# (so tasks drain first):
#   Weekdays  RDS start 17:55, ECS start 18:00, ECS stop 22:00, RDS stop 22:05
#   Weekends  RDS start 13:55, ECS start 14:00, ECS stop 20:00, RDS stop 20:05
#
# Uses EventBridge Scheduler universal targets — no Lambda required.
#

locals {
  enable_ecs_schedule = var.env == "dev"
}

# IAM role that EventBridge Scheduler assumes to call ECS + RDS APIs
resource "aws_iam_role" "ecs_scheduler" {
  count = local.enable_ecs_schedule ? 1 : 0
  name  = "${local.name}-ecs-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_scheduler" {
  count = local.enable_ecs_schedule ? 1 : 0
  name  = "${local.name}-ecs-scheduler"
  role  = aws_iam_role.ecs_scheduler[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:UpdateService"]
        Resource = [
          aws_ecs_service.backend.id,
          aws_ecs_service.frontend.id,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["rds:StartDBInstance", "rds:StopDBInstance"]
        Resource = [aws_db_instance.main.arn]
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Helper locals
# ---------------------------------------------------------------------------
locals {
  schedule_tz       = "Europe/Warsaw"
  scheduler_arn     = local.enable_ecs_schedule ? aws_iam_role.ecs_scheduler[0].arn : ""
  cluster_name      = aws_ecs_cluster.main.name
  backend_svc_name  = aws_ecs_service.backend.name
  frontend_svc_name = aws_ecs_service.frontend.name
  rds_identifier    = aws_db_instance.main.identifier

  ecs_schedules = local.enable_ecs_schedule ? {
    backend-start-weekday  = { cron = "cron(0 18 ? * MON-FRI *)", service = local.backend_svc_name,  desired = 1 }
    backend-stop-weekday   = { cron = "cron(0 22 ? * MON-FRI *)", service = local.backend_svc_name,  desired = 0 }
    backend-start-weekend  = { cron = "cron(0 14 ? * SAT-SUN *)", service = local.backend_svc_name,  desired = 1 }
    backend-stop-weekend   = { cron = "cron(0 20 ? * SAT-SUN *)", service = local.backend_svc_name,  desired = 0 }
    frontend-start-weekday = { cron = "cron(0 18 ? * MON-FRI *)", service = local.frontend_svc_name, desired = 1 }
    frontend-stop-weekday  = { cron = "cron(0 22 ? * MON-FRI *)", service = local.frontend_svc_name, desired = 0 }
    frontend-start-weekend = { cron = "cron(0 14 ? * SAT-SUN *)", service = local.frontend_svc_name, desired = 1 }
    frontend-stop-weekend  = { cron = "cron(0 20 ? * SAT-SUN *)", service = local.frontend_svc_name, desired = 0 }
  } : {}

  rds_schedules = local.enable_ecs_schedule ? {
    rds-start-weekday = { cron = "cron(55 17 ? * MON-FRI *)", action = "startDBInstance" }
    rds-stop-weekday  = { cron = "cron(5 22 ? * MON-FRI *)",  action = "stopDBInstance"  }
    rds-start-weekend = { cron = "cron(55 13 ? * SAT-SUN *)", action = "startDBInstance" }
    rds-stop-weekend  = { cron = "cron(5 20 ? * SAT-SUN *)",  action = "stopDBInstance"  }
  } : {}
}

# --- ECS schedules ---
resource "aws_scheduler_schedule" "ecs" {
  for_each = local.ecs_schedules

  name                         = "${local.name}-${each.key}"
  schedule_expression          = each.value.cron
  schedule_expression_timezone = local.schedule_tz

  flexible_time_window { mode = "OFF" }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:ecs:updateService"
    role_arn = local.scheduler_arn

    input = jsonencode({
      Cluster      = local.cluster_name
      Service      = each.value.service
      DesiredCount = each.value.desired
    })
  }
}

# --- RDS schedules ---
resource "aws_scheduler_schedule" "rds" {
  for_each = local.rds_schedules

  name                         = "${local.name}-${each.key}"
  schedule_expression          = each.value.cron
  schedule_expression_timezone = local.schedule_tz

  flexible_time_window { mode = "OFF" }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:rds:${each.value.action}"
    role_arn = local.scheduler_arn

    input = jsonencode({
      DbInstanceIdentifier = local.rds_identifier
    })
  }
}
