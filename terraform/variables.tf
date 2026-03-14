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
  validation {
    condition     = length(trimspace(var.db_password)) >= 8
    error_message = "db_password must be at least 8 characters (use TF_VAR_db_password with the real existing RDS password)."
  }
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
  default     = "placeholder" # overridden by CI/CD on deploy
}

variable "frontend_image" {
  description = "Frontend Docker image URI"
  type        = string
  default     = "placeholder" # overridden by CI/CD on deploy
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
  validation {
    condition     = length(trimspace(var.django_secret_key)) > 0
    error_message = "django_secret_key must be provided (use -var-file=secrets.tfvars or TF_VAR_django_secret_key)."
  }
}

variable "cors_allowed_origins" {
  description = "Comma-separated CORS_ALLOWED_ORIGINS for the backend (e.g. https://app.example.com)"
  type        = string
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key for AI patient summary endpoint (set in Secrets Manager after first apply)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "reminder_email_provider" {
  description = "Reminder email provider (internal or sendgrid)"
  type        = string
  default     = "internal"
  validation {
    condition     = contains(["internal", "sendgrid"], var.reminder_email_provider)
    error_message = "reminder_email_provider must be one of: internal, sendgrid."
  }
}

variable "reminder_sms_provider" {
  description = "Reminder SMS provider (internal or twilio)"
  type        = string
  default     = "internal"
  validation {
    condition     = contains(["internal", "twilio"], var.reminder_sms_provider)
    error_message = "reminder_sms_provider must be one of: internal, twilio."
  }
}

variable "reminder_sendgrid_api_key" {
  description = "SendGrid API key for reminder email delivery"
  type        = string
  sensitive   = true
  default     = ""
}

variable "reminder_sendgrid_from_email" {
  description = "SendGrid sender email for reminder messages"
  type        = string
  default     = ""
}

variable "reminder_sendgrid_from_name" {
  description = "SendGrid sender display name for reminder messages"
  type        = string
  default     = "Veto Clinic"
}

variable "reminder_sendgrid_webhook_secret" {
  description = "HMAC secret used to verify SendGrid reminder webhooks"
  type        = string
  sensitive   = true
  default     = ""
}

variable "reminder_twilio_account_sid" {
  description = "Twilio account SID used for reminder SMS delivery"
  type        = string
  sensitive   = true
  default     = ""
}

variable "reminder_twilio_auth_token" {
  description = "Twilio auth token used for reminder SMS delivery"
  type        = string
  sensitive   = true
  default     = ""
}

variable "reminder_twilio_from_number" {
  description = "Twilio sender number for reminder SMS delivery"
  type        = string
  default     = ""
}

variable "reminder_twilio_status_callback_url" {
  description = "Optional Twilio status callback URL for reminder delivery updates"
  type        = string
  default     = ""
}

variable "reminder_twilio_webhook_secret" {
  description = "HMAC secret used to verify Twilio reminder webhooks"
  type        = string
  sensitive   = true
  default     = ""
}

variable "reminder_webhook_token" {
  description = "Fallback shared token for reminder webhooks (legacy provider integrations)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "overdue_invoices_schedule_expression" {
  description = "EventBridge schedule for mark_overdue_invoices command"
  type        = string
  default     = "cron(0 1 * * ? *)"
}

variable "reminder_enqueue_schedule_expression" {
  description = "EventBridge schedule for enqueue_reminders command"
  type        = string
  default     = "rate(30 minutes)"
}

variable "reminder_process_schedule_expression" {
  description = "EventBridge schedule for process_reminders command"
  type        = string
  default     = "rate(5 minutes)"
}
