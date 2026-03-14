# Deployment

## Overview

Veto is deployed on AWS. Infrastructure is defined in Terraform (`terraform/`). Deployments are triggered via GitHub Actions.

```
GitHub push to main
  └─▶ CI workflow (tests, lint)
        └─▶ Deploy workflow (on CI success)
              ├─▶ Build & push backend Docker image → ECR
              ├─▶ Build & push frontend Docker image → ECR
              ├─▶ Run DB migrations (ECS one-off task)
              ├─▶ Deploy backend ECS service
              └─▶ Deploy frontend ECS service
```

---

## Environments

| Environment | Trigger | ECS cluster |
|---|---|---|
| **dev** | Automatic on every merge to `main` (after CI passes) | `veto-dev-cluster` |
| **prod** | Manual via GitHub Actions → "Run workflow" | `veto-prod-cluster` |

---

## CI Pipeline (`.github/workflows/ci.yml`)

Runs on every push and pull request:
1. `ruff check .` — linting
2. `black --check .` — formatting
3. `pytest` — all tests

Deployment only proceeds if CI passes.

---

## Deploy Pipeline (`.github/workflows/deploy.yml`)

### Authentication

Uses **GitHub Actions OIDC** (no stored AWS credentials). GitHub Actions assumes the IAM role `veto-github-actions` via OIDC federation. This role has permissions for:
- ECR push
- ECS describe/register/run/deploy
- Secrets Manager read

The OIDC provider and role are defined in `terraform/iam.tf`.

### Steps

1. **Build & push images** — Docker images tagged with `sha-<commit>` and `<env>-latest`
2. **Render task definition** — injects the new image digest into the existing ECS task definition JSON
3. **Run migrations** — registers the new task definition, runs `python manage.py migrate --no-input` as a Fargate one-off task, waits for exit code 0
4. **Deploy backend** — updates the ECS service with the new task definition
5. **Deploy frontend** — same for the frontend service

### Deploying to Production

Go to **GitHub → Actions → Deploy → Run workflow → select `prod`**.

---

## Infrastructure (Terraform)

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Key resources:
- `ecs.tf` — ECS cluster, services, task definitions
- `ecr.tf` — ECR repositories for backend and frontend
- `rds.tf` — PostgreSQL RDS instance
- `secrets.tf` — Secrets Manager secrets (`db_password`, `django_secret_key`, `cors_allowed_origins`, `openai_api_key`)
- `iam.tf` — GitHub Actions OIDC provider + IAM role
- `alb.tf` — Application Load Balancer, listeners, target groups

### Important: Secrets lifecycle

All secrets in `secrets.tf` have:
```hcl
lifecycle {
  ignore_changes = [secret_string]
}
```

This prevents `terraform apply` from overwriting secrets that were set manually in AWS. **Never pass real credentials as Terraform variables** — set them directly in AWS Secrets Manager after the first `apply`.

---

## Database Migrations

Migrations run automatically on every deploy (before the ECS service update). They run as a Fargate one-off task using the new Docker image — this guarantees migrations run against the same code being deployed.

If you need to run migrations manually (e.g. after a hotfix):

```bash
aws ecs run-task \
  --cluster veto-dev-cluster \
  --task-definition veto-dev-backend \
  --launch-type FARGATE \
  --network-configuration "$(aws ecs describe-services \
      --cluster veto-dev-cluster \
      --services veto-dev-backend \
      --query 'services[0].networkConfiguration' \
      --output json)" \
  --overrides '{"containerOverrides":[{"name":"backend","command":["python","manage.py","migrate","--no-input"]}]}'
```

---

## Secrets Management

Secrets are stored in AWS Secrets Manager and injected into ECS tasks as environment variables at runtime.

| Secret | Key | Used by |
|---|---|---|
| `veto-<env>/db-password` | `RDS_PASSWORD` | Django database config |
| `veto-<env>/django-secret-key` | `SECRET_KEY` | Django settings |
| `veto-<env>/cors-allowed-origins` | `CORS_ALLOWED_ORIGINS` | Django CORS config |
| `veto-<env>/openai-api-key` | `OPENAI_API_KEY` | AI patient summary endpoint |

To update a secret value:
```bash
aws secretsmanager put-secret-value \
  --secret-id veto-dev/openai-api-key \
  --secret-string "sk-..."
```

After rotating secret values, force backend deployment so ECS picks the latest value:

```bash
aws ecs update-service \
  --cluster veto-dev-cluster \
  --service veto-dev-backend \
  --force-new-deployment
```

Verify the backend task definition includes `OPENAI_API_KEY` secret injection:

```bash
aws ecs describe-task-definition \
  --task-definition veto-dev-backend \
  --query "taskDefinition.containerDefinitions[?name=='backend'].secrets[*].name" \
  --output text
```

---

## Rollback

To roll back to a previous image, re-run the deploy workflow on an earlier commit, or manually update the ECS service in the AWS console to use a previous task definition revision.
