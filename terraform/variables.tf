variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "env" {
  description = "Environment name (dev or prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be 'dev' or 'prod'."
  }
}

variable "app_name" {
  description = "Application name used for resource naming"
  type        = string
  default     = "veto"
}

# --- Database ---
variable "db_password" {
  description = "RDS master password (store in Secrets Manager, pass via TF_VAR_db_password)"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

# --- ECS ---
variable "backend_image" {
  description = "Backend Docker image URI (e.g. 123456789.dkr.ecr.eu-central-1.amazonaws.com/veto-backend:sha-abc)"
  type        = string
  default     = "placeholder"  # overridden by CI/CD on deploy
}

variable "frontend_image" {
  description = "Frontend Docker image URI"
  type        = string
  default     = "placeholder"  # overridden by CI/CD on deploy
}

variable "backend_task_cpu" {
  description = "ECS task CPU units for backend (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "backend_task_memory" {
  description = "ECS task memory in MB for backend"
  type        = number
  default     = 512
}

variable "frontend_task_cpu" {
  description = "ECS task CPU units for frontend"
  type        = number
  default     = 256
}

variable "frontend_task_memory" {
  description = "ECS task memory in MB for frontend"
  type        = number
  default     = 512
}

variable "django_secret_key" {
  description = "Django SECRET_KEY (store in Secrets Manager, pass via TF_VAR_django_secret_key)"
  type        = string
  sensitive   = true
}

variable "cors_allowed_origins" {
  description = "Comma-separated CORS_ALLOWED_ORIGINS for the backend (e.g. https://app.example.com)"
  type        = string
  default     = ""
}
