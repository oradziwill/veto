env               = "dev"
region            = "eu-central-1"

# RDS
db_instance_class = "db.t3.micro"

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
