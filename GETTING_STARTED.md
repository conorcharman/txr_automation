# Getting Started: Windows Local Development (Without Conda)

This guide walks you through setting up **TXR Automation** on a Windows PC for local development without using Conda.

**Strategy:** Use Docker Compose to run PostgreSQL, Redis, and the backend services, whilst running the frontend and Python dependencies locally for fast development.

---

## ⚠️ Important: Corporate Network Setup

This project runs behind a corporate SSL-inspection proxy. **Before proceeding, ask Matt W for the following three files:**

1. **`.npmrc`** — npm proxy configuration (provides corporate proxy credentials for npm)
2. **`zscaler-ca.crt`** — Zscaler/corporate SSL certificate for Docker builds
3. **`pip-trusted-certs.pem`** — Corporate certificate bundle for Python pip

**Copy these files to the project root** (same directory as `docker-compose.yml`):

```powershell
# Example: After receiving files from Matt W
Copy-Item ".\Downloads\.npmrc" .
Copy-Item ".\Downloads\zscaler-ca.crt" .
Copy-Item ".\Downloads\pip-trusted-certs.pem" .
```

Additionally, **configure Docker Desktop proxy:**

1. Open Docker Desktop → Settings → Resources → Proxies
2. Enable **Manual proxy configuration**
3. Set:
   - **Web Server (HTTP):** `https://soc-fg.core2-dev.ajbbuild.uk:443`
   - **Secure Web Server (HTTPS):** `https://soc-fg.core2-dev.ajbbuild.uk:443`
   - **Bypass proxy for:** `localhost,127.0.0.1,.local`
4. Click **Apply & Restart**

---

## Prerequisites

Before you start, install the following tools on your Windows machine:

### 1. Python 3.10+

- Download from [python.org](https://www.python.org/downloads/)
- Choose Python 3.10, 3.11, or 3.12 (latest stable)
- **Important:** During installation, check the box: "Add Python to PATH"
- Verify installation:

```powershell
python --version
```

### 2. Node.js (for React frontend)

- Download from [nodejs.org](https://nodejs.org/)
- Choose the LTS (Long-term Support) version
- This installs both `node` and `npm`
- Verify installation:

```powershell
node --version
npm --version
```

### 3. Docker Desktop

- Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
- Install and start it
- Verify installation:

```powershell
docker --version
docker run hello-world
```

### 4. Git

- Download from [git-scm.com](https://git-scm.com/download/win)
- Use default installation options
- Verify:

```powershell
git --version
```

---

## Setup Steps

### Step 1: Clone the Repository

```powershell
# Choose a location for the project
cd C:\Users\YourUsername\Projects

# Clone the repository
git clone https://github.com/conorcharman/txr_automation.git
cd txr_automation
```

### Step 2: Create Python Virtual Environment

Use Python's built-in `venv` (no Conda needed):

```powershell
# Create virtual environment
python -m venv venv

# Activate it (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate it (Windows Command Prompt)
.\venv\Scripts\activate.bat

# You should see (venv) at the start of your terminal prompt
```

**Note:** If you get an execution policy error in PowerShell, run this once:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 3: Install Python Dependencies

```powershell
# Make sure (venv) is active
# Install the project
pip install -e .

# Install API-specific dependencies
pip install -r api/requirements.txt
```

### Step 4: Install Frontend Dependencies

```powershell
# Navigate to web directory
cd web

# Install npm packages
npm install

# Return to project root
cd ..
```

### Step 5: Configure Environment Variables

```powershell
# Copy the environment template
Copy-Item config\templates\environments\.env.example .env

# Edit the .env file with Notepad or your editor
notepad .env
```

Set these key variables:

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=txr_automation

# Redis (Docker service, no change needed)
REDIS_URL=redis://redis:6379

# FastAPI (Docker service)
API_HOST=0.0.0.0
API_PORT=8000

# Optional: Set log level
LOG_LEVEL=INFO
```

---

## Running the Application

The simplest way is to use **Docker Compose** for backend services and run the frontend + API locally for development.

### Option A: Docker Compose (Recommended) + Local Frontend

This setup runs PostgreSQL, Redis, Celery worker, and beat scheduler in Docker, whilst you run the React dev server locally.

**Terminal 1: Start Docker Services**

```powershell
# Make sure Docker Desktop is running
# Start all backend services
docker compose up

# You should see output from redis, db, api, worker, and beat services
```

**Terminal 2: Start React Frontend Dev Server**

```powershell
# In a new terminal, navigate to web directory
cd web

# Activate venv first (if not already active)
..\venv\Scripts\Activate.ps1

# Start development server
npm run dev
```

You should see output like:

```
VITE v5.x.x  ready in x ms

➜  Local:   http://localhost:5173/
```

**Terminal 3 (Optional): Run Python Scripts/Tests**

```powershell
# With (venv) active, run tests or scripts
# Example: Run backend tests
pytest tests/test_api/ -v

# Example: Run a console script
validate-buyer --config config/local/buyer_id.yaml
```

### Option B: Local Full Stack (Without Docker)

If you prefer to run everything locally without Docker:

**Terminal 1: Start Python Backend API**

```powershell
# With (venv) active, from project root
# You'll need PostgreSQL and Redis running natively on Windows first
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2: Start React Frontend Dev Server**

```powershell
cd web
npm run dev
```

**Terminal 3: Start Celery Worker**

```powershell
# With (venv) active
celery -A api.tasks worker --loglevel=info
```

This requires you to have installed PostgreSQL 16 and Redis natively on Windows (see **Local Setup** section below).

---

## Accessing the Application

Once services are running (using Docker Compose or local):

| Service | URL |
|---------|-----|
| **Web UI** | http://localhost:5173 |
| **API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **API Docs (ReDoc)** | http://localhost:8000/redoc |

---

## Verification Checklist

```powershell
# Verify prerequisites installed
python --version
node --version
docker --version
git --version

# With (venv) active, verify Python dependencies
pip list | grep -E "fastapi|pandas|pytest"

# With Docker running, verify services
docker ps

# Check React dev server runs
cd web && npm run dev
# You should see: ➜ Local: http://localhost:5173/
```

---

## Local Setup (if NOT using Docker)

If you want to run everything locally without Docker, you'll need to install PostgreSQL and Redis natively:

### PostgreSQL 16 (Local Installation)

- Download from [postgresql.org](https://www.postgresql.org/download/windows/)
- Run installer, remember the superuser password
- Choose port **5432** (default)
- Verify: `psql --version`
- Add to PATH if needed: `C:\Program Files\PostgreSQL\16\bin`

### Redis (Local Installation)

Option 1: **WSL2**

```powershell
wsl --install
# Inside WSL terminal:
sudo apt-get update
sudo apt-get install redis-server
redis-server
```

Option 2: **Memurai (Native Windows)**

- Download [Memurai](https://www.memurai.com/)
- Install and verify: `redis-cli ping`

### Create Local Database

```powershell
psql -U postgres -c "CREATE DATABASE txr_automation;"
```

### Run Database Migrations

```powershell
# With (venv) active
alembic upgrade head
```

---

## Common Issues & Troubleshooting

### Issue: "python: command not found"

**Solution:** Python not in PATH. Reinstall Python and ensure "Add Python to PATH" is checked.

### Issue: "docker: command not found" or Docker not running

**Solution:** 
1. Ensure Docker Desktop is installed and running
2. Restart Docker Desktop if needed
3. Check it's running: `docker ps`

### Issue: `docker compose up` fails to start services

**Solution:** Check Docker Desktop is running and you have enough disk space:

```powershell
# View service logs
docker compose logs -f

# Stop and remove containers, volumes
docker compose down -v

# Retry
docker compose up
```

### Issue: "Failed to connect to database" when using Docker

**Solution:** Services may need time to start. Wait 10-15 seconds then retry. Check logs:

```powershell
docker compose logs db
docker compose logs redis
```

### Issue: "Module not found" errors when running frontend/tests

**Solution:** Activate virtual environment:

```powershell
# Verify (venv) appears at start of terminal prompt
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -e .
pip install -r api/requirements.txt
```

### Issue: npm packages won't install

**Solution:** Clear cache and retry:

```powershell
cd web
npm cache clean --force
npm install
cd ..
```

### Issue: Port already in use (e.g., "Address already in use :5173")

**Solution:** Stop conflicting services or use different port:

```powershell
# Find what's using the port
netstat -ano | findstr :5173

# Stop docker compose
docker compose down

# Or use different port for Vite
cd web
npm run dev -- --port 3000
```

### Issue: API shows "Connection refused" when calling from frontend

**Solution:** Update `.env` to use Docker service name:

```env
# When using Docker Compose, use the service name as hostname
API_URL=http://api:8000
VITE_API_URL=http://localhost:8000
```

For local development, `http://localhost:8000` should work.

### Issue: Can't connect to Docker container from localhost

**Solution:** You may need to check Docker network. Docker Compose automatically creates a bridge network. Services should be accessible at `localhost` on their exposed ports.

### Issue: TypeScript errors: "Cannot find module '@/lib/utils'"

**Solution:** The `web/src/lib/utils.ts` file must exist. If missing, create it with:

```powershell
# From project root
mkdir -p web\src\lib
```

Then create `web/src/lib/utils.ts` with:

```typescript
/**
 * Utility function to combine class names conditionally.
 * Commonly used with Tailwind CSS and shadcn/ui components.
 */
export function cn(...classes: (string | undefined | boolean | null)[]): string {
  return classes
    .filter((cls) => typeof cls === "string" && cls.length > 0)
    .join(" ")
}
```

This file provides the `cn` function used by all shadcn/ui components for conditional Tailwind CSS class names.

---

## Development Workflow

### Running Tests

```powershell
# With (venv) active

# Backend API tests
pytest tests/test_api/ -v

# Accuracy testing module tests
pytest tests/test_accuracy_testing/ -v

# All backend tests with coverage
pytest tests/ --cov=src --cov=api --cov-report=html

# Frontend tests
cd web && npm run test && cd ..
```

### Code Quality Checks

```powershell
# Format code
python -m black src/ tests/ api/
python -m isort src/ tests/ api/

# Lint
python -m flake8 src/ tests/ api/

# Type checking
python -m mypy api/ --ignore-missing-imports

# Frontend lint
cd web && npm run lint && cd ..
```

### Running Console Scripts

Once installed, you can run 22+ command-line tools:

```powershell
# With (venv) active

# Accuracy testing
validate-buyer --config config/local/buyer_id.yaml
validate-seller --config config/local/seller_id.yaml

# SQL extraction
generate-sql-extract --config config/local/sql_extract.yaml --mode batch

# Regulatory data
firds-refresh --config config/local/firds_config.yaml
gleif-refresh --config config/local/gleif_config.yaml

# View help
validate-buyer --help
```

### Stopping the Application

When you're done developing:

```powershell
# If using Docker Compose:
# In the terminal running 'docker compose up', press Ctrl+C
# Optionally, clean up containers:
docker compose down

# Optionally, remove volumes (clears database):
docker compose down -v
```

```powershell
# For local services:
# In each terminal, press Ctrl+C to stop:
# Terminal 1 (API): Ctrl+C
# Terminal 2 (Frontend): Ctrl+C
# Terminal 3 (Celery): Ctrl+C
```


---

## Next Steps

- Read [ARCHITECTURE.md](./ARCHITECTURE.md) for system design
- Check [documentation/guides/](./documentation/guides/) for feature guides
- Run `pytest tests/` to ensure all tests pass
- Explore the API docs at http://localhost:8000/docs

---

## Getting Help

- Check [README.md](./README.md) for general project info
- Review error messages carefully — they usually indicate the fix needed
- Refer to the troubleshooting section above
- Check terminal output for detailed error logs

---

## Additional Resources

- [Python docs](https://docs.python.org/3.10/)
- [FastAPI docs](https://fastapi.tiangolo.com/)
- [React docs](https://react.dev)
- [PostgreSQL docs](https://www.postgresql.org/docs/16/)
- [Redis docs](https://redis.io/docs/)
- [npm docs](https://docs.npmjs.com/)




