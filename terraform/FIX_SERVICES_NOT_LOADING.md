# Fix: Services Not Loading on AWS (301 Redirect / Timeout)

## Problem
When opening a new visit on AWS, services fail to load with error:
- Browser shows: `Ładowanie usług...` → `Nie udało się załadować usług`
- Console error: `timeout of 30000ms exceeded` or `301 Moved Permanently`
- Request URL: `http://veto-dev-alb-xxx.elb.amazonaws.com/api/billing/services/`

## Root Cause
The frontend container's `BACKEND_URL` was set to the ALB URL (`http://${aws_lb.main.dns_name}`), creating a circular routing problem:
1. Browser → ALB → Frontend
2. Frontend nginx proxy → `BACKEND_URL` (ALB) → Frontend again
3. Result: 301 redirect or timeout

## Solution
Use **AWS Cloud Map (ECS Service Discovery)** to allow the frontend to call the backend directly via an internal DNS name, bypassing the ALB for internal API calls.

### Changes Made

#### 1. Added Service Discovery (`terraform/service_discovery.tf`)
- Created private DNS namespace: `veto-{env}-internal`
- Registered backend service as `backend.veto-{env}-internal:8000`

#### 2. Updated Backend Service (`terraform/ecs.tf`)
- Added `service_registries` block to register backend with Cloud Map

#### 3. Updated Frontend Environment (`terraform/ecs.tf`)
- Changed `BACKEND_URL` from ALB to service discovery DNS:
  ```
  BACKEND_URL=http://backend.veto-{env}-internal:8000
  ```

### Deployment Steps

1. **Apply Terraform changes**
   ```bash
   cd terraform
   terraform init
   terraform plan -var-file=dev.tfvars
   terraform apply -var-file=dev.tfvars
   ```

2. **Force new deployment** (to pick up new task definitions)
   ```bash
   aws ecs update-service \
     --cluster veto-dev-cluster \
     --service veto-dev-backend \
     --force-new-deployment

   aws ecs update-service \
     --cluster veto-dev-cluster \
     --service veto-dev-frontend \
     --force-new-deployment
   ```

3. **Verify**
   - Wait 2-3 minutes for tasks to restart
   - Open the app and try to start a new visit
   - Services should load successfully
   - Check browser DevTools Network tab: `/api/billing/services/` should return 200 OK

### How It Works Now

**Before (broken):**
```
Browser → ALB → Frontend → nginx proxy → BACKEND_URL (ALB) → Frontend (loop/301)
```

**After (fixed):**
```
Browser → ALB → Frontend → nginx proxy → backend.veto-dev-internal:8000 → Backend (direct)
```

### Rollback
If needed, revert the Terraform changes:
```bash
git checkout main -- terraform/
terraform apply -var-file=dev.tfvars
```

### Alternative Solutions (Not Implemented)
1. **Use ALB Internal Listener**: Frontend could use ALB's DNS, but ALB would need a separate listener or target group routing rule to avoid loops.
2. **Build-time API URL**: Set `VITE_API_URL` at build time to the public ALB URL, making the app call the backend directly from the browser (requires CORS configuration and exposes backend publicly).

## Notes
- The ALB still handles external traffic (browser → frontend, browser → backend via `/api/*`)
- Service Discovery DNS only works within the VPC
- Frontend nginx now proxies internal API calls directly to the backend service
- Health checks and logging remain unchanged
