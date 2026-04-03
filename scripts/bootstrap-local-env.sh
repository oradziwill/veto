#!/usr/bin/env bash
# Creates repo-root .env from .env.example if missing, and appends safe local defaults for lab ingest.
# Does NOT overwrite an existing .env (your secrets stay intact).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  echo "OK: .env already exists — left unchanged."
  echo "    To add lab defaults manually, see .env.example (LAB_INGESTION_*)."
  exit 0
fi

cp .env.example .env
{
  echo ""
  echo "# --- bootstrap-local-env.sh (local dev; safe defaults) ---"
  echo "LAB_INGESTION_S3_ENABLED=false"
  echo "# On prod/staging: remove the line above or set true, and configure DOCUMENTS_DATA_S3_BUCKET (see LAB_INTEGRATION.md)."
} >> .env

echo "Created $ROOT/.env from .env.example + LAB_INGESTION_S3_ENABLED=false"
echo "Next: edit .env if you need Postgres, ALLOWED_HOSTS, or S3."
