#
# Operational baseline:
# - scheduled overdue invoice marking
# - CloudWatch alarms for backend health
#

data "aws_iam_policy_document" "eventbridge_ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge_ecs_runner" {
  name               = "${local.name}-eventbridge-ecs-runner"
  assume_role_policy = data.aws_iam_policy_document.eventbridge_ecs_assume_role.json
}

resource "aws_iam_role_policy" "eventbridge_ecs_runner" {
  name = "${local.name}-eventbridge-ecs-runner"
  role = aws_iam_role.eventbridge_ecs_runner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:DescribeTasks",
        ]
        Resource = [
          aws_ecs_task_definition.backend.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole",
        ]
        Resource = [
          aws_iam_role.ecs_execution.arn,
          aws_iam_role.ecs_task.arn,
        ]
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "mark_overdue_invoices_daily" {
  name                = "${local.name}-mark-overdue-invoices"
  description         = "Runs mark_overdue_invoices command on schedule"
  schedule_expression = var.overdue_invoices_schedule_expression
}

resource "aws_cloudwatch_event_target" "mark_overdue_invoices_daily" {
  rule      = aws_cloudwatch_event_rule.mark_overdue_invoices_daily.name
  target_id = "mark-overdue-invoices"
  arn       = aws_ecs_cluster.main.arn
  role_arn  = aws_iam_role.eventbridge_ecs_runner.arn

  ecs_target {
    launch_type         = "FARGATE"
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.backend.arn
    platform_version    = "LATEST"

    network_configuration {
      subnets          = aws_subnet.private[*].id
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = false
    }
  }

  input = jsonencode({
    containerOverrides = [
      {
        name    = "backend"
        command = ["python", "manage.py", "mark_overdue_invoices"]
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "alb_backend_5xx" {
  alarm_name          = "${local.name}-alb-backend-5xx"
  alarm_description   = "Backend target 5xx errors are above threshold"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 5
  threshold           = 10
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "ecs_backend_cpu_high" {
  alarm_name          = "${local.name}-ecs-backend-cpu-high"
  alarm_description   = "Backend ECS service CPU is high"
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 10
  threshold           = 80
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.backend.name
  }
}

resource "aws_cloudwatch_metric_alarm" "ecs_backend_memory_high" {
  alarm_name          = "${local.name}-ecs-backend-memory-high"
  alarm_description   = "Backend ECS service memory is high"
  namespace           = "AWS/ECS"
  metric_name         = "MemoryUtilization"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 10
  threshold           = 85
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.backend.name
  }
}

resource "aws_cloudwatch_metric_alarm" "ecs_backend_running_tasks_low" {
  alarm_name          = "${local.name}-ecs-backend-running-low"
  alarm_description   = "Backend ECS running task count dropped below 1"
  namespace           = "AWS/ECS"
  metric_name         = "RunningTaskCount"
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.backend.name
  }
}
