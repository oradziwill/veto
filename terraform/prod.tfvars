env    = "prod"
region = "eu-central-1"

# Shared global resources are managed in this state after import.
manage_shared_ecr_resources    = true
manage_shared_ci_iam_resources = true

# RDS bootstrap settings for this account plan.
db_instance_class           = "db.t3.micro"
rds_backup_retention_period = 0
rds_multi_az                = false
rds_deletion_protection     = false
rds_skip_final_snapshot     = true

# ECS — backend
backend_task_cpu    = 512
backend_task_memory = 1024

# ECS — frontend
frontend_task_cpu    = 256
frontend_task_memory = 512

# Reminder providers (guardrails + smoke checks are provider-aware)
reminder_email_provider = "internal"
reminder_sms_provider   = "internal"

# Sensitive values — pass via environment variables at apply time:
#   export TF_VAR_db_password="..."
#   export TF_VAR_django_secret_key="..."
# Do NOT commit actual values here.
