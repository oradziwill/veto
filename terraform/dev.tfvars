env    = "dev"
region = "eu-central-1"

# Dev state manages shared global resources.
manage_shared_ecr_resources    = true
manage_shared_ci_iam_resources = true

# RDS
db_instance_class           = "db.t3.micro"
rds_backup_retention_period = 1
rds_multi_az                = false
rds_deletion_protection     = false
rds_skip_final_snapshot     = true

# ECS — backend
backend_task_cpu    = 256
backend_task_memory = 512

# ECS — frontend
frontend_task_cpu    = 256
frontend_task_memory = 512

# Sensitive values — pass via environment variables at apply time:
#   export TF_VAR_db_password="..."
#   export TF_VAR_django_secret_key="..."
# Do NOT commit actual values here.
