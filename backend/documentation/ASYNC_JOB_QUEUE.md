# Async job queue (Redis + RQ)

Background work uses **[django-rq](https://github.com/rq/django-rq)** on Redis. The same Redis deployment as Django cache (`REDIS_URL`) can be used; optionally set **`RQ_REDIS_URL`** to isolate queue traffic (e.g. different logical DB index in the URL path).

## Configuration

| Variable | Effect |
| -------- | ------ |
| `REDIS_URL` / `DJANGO_REDIS_URL` | If set, **report export jobs are enqueued on create** by default (`RQ_REPORT_EXPORT_ENQUEUE` defaults to on). Also used as RQ URL when `RQ_REDIS_URL` is unset. |
| `RQ_REDIS_URL` | Explicit Redis URL for RQ (takes precedence over `REDIS_URL` for queue connection). |
| `RQ_REPORT_EXPORT_ENQUEUE` | `1` / `0` — force enqueue on/off regardless of default. |

When no Redis URL is set in the environment, **enqueue-on-create is off**; exports still run via `POST .../process-pending/` or `python manage.py process_report_exports`.

Default queue connection when vars are missing points at `redis://127.0.0.1:6379/15` so a local worker can run without extra env.

## Worker process

```bash
cd backend
python manage.py rqworker default
```

Production (see `Procfile`):

```text
worker: python manage.py rqworker default --verbosity 1
```

Run at least one worker container/service when `RQ_REPORT_EXPORT_ENQUEUE` is enabled, or jobs will remain `pending` until cron/management commands process them.

## Current tasks

- **`report_export_job_task`** — processes one `ReportExportJob` row (`apps.reports.rq_tasks`).

Processing uses `select_for_update(skip_locked=True)` so duplicate enqueues or concurrent workers do not double-run the same job.
