data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Execution role: lets ECS pull images from ECR and write logs to CloudWatch
resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name}-ecs-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow ECS to read secrets from Secrets Manager
resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "${local.name}-ecs-execution-secrets"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        aws_secretsmanager_secret.django_secret_key.arn,
        aws_secretsmanager_secret.db_password.arn,
        aws_secretsmanager_secret.app_secrets.arn,
      ]
    }]
  })
}

# ---------------------------------------------------------------------------
# GitHub Actions OIDC – allows the deploy workflow to push images to ECR
# and deploy to ECS without storing long-lived AWS credentials in GitHub.
# ---------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.manage_shared_ci_iam_resources ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_actions_assume_role" {
  count = var.manage_shared_ci_iam_resources ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:oradziwill/veto:*"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  count = var.manage_shared_ci_iam_resources ? 1 : 0

  name               = "veto-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role[0].json
}

resource "aws_iam_role_policy" "github_actions" {
  count = var.manage_shared_ci_iam_resources ? 1 : 0

  name = "veto-github-actions-policy"
  role = aws_iam_role.github_actions[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "ECRPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ]
        Resource = [
          "arn:aws:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/veto-backend",
          "arn:aws:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/veto-frontend",
        ]
      },
      {
        Sid    = "ECS"
        Effect = "Allow"
        Action = [
          "ecs:DescribeTaskDefinition",
          "ecs:RegisterTaskDefinition",
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:RunTask",
          "ecs:DescribeTasks",
        ]
        Resource = "*"
      },
      {
        Sid    = "ELBReadForSmokeChecks"
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:DescribeLoadBalancers",
        ]
        Resource = "*"
      },
      {
        Sid    = "PassRoleToECS"
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/veto-*",
        ]
      },
    ]
  })
}

# Task role: permissions the application itself needs at runtime
resource "aws_iam_role" "ecs_task" {
  name               = "${local.name}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

# Allow ECS Exec (aws ecs execute-command) via SSM
resource "aws_iam_role_policy" "ecs_task_exec_command" {
  name = "${local.name}-ecs-task-exec-command"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel"
      ]
      Resource = "*"
    }]
  })
}

# Document ingestion: ECS task needs S3 GetObject/PutObject (and ListBucket) on documents bucket
resource "aws_iam_role_policy" "ecs_task_documents_s3" {
  count = length(trimspace(var.documents_data_s3_bucket_name)) > 0 ? 1 : 0

  name = "${local.name}-ecs-task-documents-s3"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = "arn:aws:s3:::${var.documents_data_s3_bucket_name}/documents_data/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = "arn:aws:s3:::${var.documents_data_s3_bucket_name}"
        Condition = {
          StringLike = {
            "s3:prefix" = ["documents_data/*"]
          }
        }
      }
    ]
  })
}
