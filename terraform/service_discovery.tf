# ECS Service Discovery (AWS Cloud Map)
# Allows frontend to reach backend via backend.veto-internal:8000

resource "aws_service_discovery_private_dns_namespace" "main" {
  name        = "${local.name}-internal"
  vpc         = aws_vpc.main.id
  description = "Private DNS namespace for ECS service discovery"
}

resource "aws_service_discovery_service" "backend" {
  name = "backend"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}
