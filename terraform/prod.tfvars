env               = "prod"
region            = "eu-central-1"

# RDS — multi-AZ, deletion protection, and 7-day backups are enabled automatically for prod
db_instance_class = "db.t3.small"

# ECS — backend
backend_task_cpu    = 512
backend_task_memory = 1024

# ECS — frontend
frontend_task_cpu    = 256
frontend_task_memory = 512

# Sensitive values — pass via environment variables at apply time:
#   export TF_VAR_db_password="..."
#   export TF_VAR_django_secret_key="..."
# Do NOT commit actual values here.
