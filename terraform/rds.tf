resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  identifier = "${local.name}-postgres"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  db_name  = "veto"
  username = "veto"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  storage_type          = "gp3"
  allocated_storage     = 20
  max_allocated_storage = 100

  # Backups retained for 7 days (prod) / 1 day (dev via tfvars)
  backup_retention_period = var.env == "prod" ? 7 : 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  multi_az            = var.env == "prod"
  deletion_protection = var.env == "prod"
  skip_final_snapshot = var.env != "prod"

  tags = { Name = "${local.name}-postgres" }
}
