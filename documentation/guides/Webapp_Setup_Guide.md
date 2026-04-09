# Web Application Setup Guide

This guide explains how to get the TXR Automation web application running for the first time
using Docker Compose.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git repository cloned locally
- No other services using ports **3000** or **8000** on your machine

---

## Step 1: Create the Environment File

The web app reads configuration from a `.env` file in the project root. A template is already
present in the repository as `.env` — review the values and update any that need changing.

The defaults work for local development, but you should generate a fresh `SECRET_KEY`:

```bash
openssl rand -hex 32
```

Replace the `SECRET_KEY` value in `.env` with the output.

The key variables and their defaults are:

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `txr` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password — change this |
| `POSTGRES_DB` | `txr_automation` | Database name |
| `DATABASE_URL` | `postgresql+asyncpg://txr:changeme@db/txr_automation` | Full async DB URL — update if password changed |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection (no change needed) |
| `SECRET_KEY` | *(generated)* | Must be a random 64-character hex string |
| `UPLOAD_DIR` | `/app/data/uploads` | Container path for uploaded files |

> **Important:** Never commit `.env` to version control. It is already listed in `.gitignore`.

---

## Step 2: Start All Services

From the project root, run:

```bash
docker compose up -d --build
```

This builds and starts five services:

| Service | Role | Port |
|---|---|---|
| `db` | PostgreSQL — job history and saved configs | internal only |
| `redis` | Redis — Celery task broker and WebSocket pub/sub | internal only |
| `api` | FastAPI backend (auto-reloads on code changes) | `8000` |
| `worker` | Celery worker — executes background jobs | none |
| `web` | React SPA served by Nginx (proxies `/api` to backend) | `3000` |

The database schema is created automatically on first startup.

---

## Step 3: Verify the Services

Check that all containers are running:

```bash
docker compose ps
```

All five services should show a `Up` status. Then confirm the API is healthy:

```bash
curl http://localhost:8000/api/health
```

A `{"status": "ok"}` (or similar) response confirms the backend is ready.

---

## Step 4: Open the Web App

Navigate to [http://localhost:3000](http://localhost:3000) in your browser.

The application includes the following sections:

- **Dashboard** — Overview of recent job activity
- **Accuracy Testing** — Run buyer/seller ID validation scripts
- **Replay** — Phase 2 and Phase 3 replay processing
- **FIRDS** — FCA FIRDS reportability lookups
- **GLEIF** — LEI entity lookups
- **Utilities** — File conversion tools
- **Jobs** — Full job history with live log streaming

---

## Viewing Job History and Logs

Go to the **Jobs** page (`/jobs`) to see all submitted jobs and their statuses.

Click any job card to open the detail view, which shows:

- Job metadata (script name, status, timestamps)
- Live log output streamed via WebSocket whilst the job is running
- A **Save Logs** button to download the log output as a text file
- A **Cancel** button for pending or running jobs

---

## Stopping the Services

```bash
docker compose down
```

To also remove the PostgreSQL data volume (resets job history):

```bash
docker compose down -v
```

---

## Rebuilding After Code Changes

The `api` service mounts `src/` and `api/` as volumes and runs with `--reload`, so Python
changes take effect immediately without rebuilding.

For frontend changes, rebuild the `web` container:

```bash
docker compose up -d --build web
```

---

## Troubleshooting

### Jobs stay in `pending` and never run

The `worker` service is not running. Check its status:

```bash
docker compose ps worker
```

If it is missing, start it:

```bash
docker compose up -d worker
```

View worker logs to diagnose errors:

```bash
docker compose logs -f worker
```

### API fails to start

Check the API logs:

```bash
docker compose logs -f api
```

Common causes:

- **Database connection error** — ensure `DATABASE_URL` in `.env` matches `POSTGRES_USER`
  and `POSTGRES_PASSWORD`.
- **Port already in use** — check nothing else is bound to port `8000`.

### Web app shows a blank page or network errors

Check that the `api` container is healthy, then restart the `web` container:

```bash
docker compose restart web
```

### Full reset

Stop all containers, remove volumes, and rebuild from scratch:

```bash
docker compose down -v
docker compose up -d --build
```
