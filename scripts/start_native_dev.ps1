$Project  = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile  = Join-Path $Project ".env"
$CondaHook = Join-Path $env:USERPROFILE "AppData\Local\anaconda3\shell\condabin\conda-hook.ps1"

function Get-EnvValue([string]$Key) {
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return $line.Substring($Key.Length + 1)
}

# Build the DB URL from the POSTGRES_* vars — same as docker-compose environment: override.
# The DATABASE_URL in .env uses a stale placeholder user and is bypassed by Docker; do the same here.
$PgUser = Get-EnvValue "POSTGRES_USER"
$PgPass = Get-EnvValue "POSTGRES_PASSWORD"
$PgDb   = Get-EnvValue "POSTGRES_DB"
if ($PgUser -and $PgPass -and $PgDb) {
    $DbUrl = "postgresql+asyncpg://${PgUser}:${PgPass}@localhost/${PgDb}"
} else {
    # Fallback: patch the URL from .env (replaces host only)
    $DbUrl = (Get-EnvValue "DATABASE_URL") -replace "@db/", "@localhost/"
}

$RedisUrl = (Get-EnvValue "REDIS_URL") -replace "://redis:", "://localhost:"
if (-not $RedisUrl) { $RedisUrl = "redis://localhost:6379/0" }

function Start-NativeWindow([string]$Title, [string[]]$Lines) {
    $tmp = Join-Path $env:TEMP "txr_$($Title -replace '[^a-zA-Z0-9]','_').ps1"
    $Lines | Set-Content -Path $tmp -Encoding UTF8
    Start-Process powershell -ArgumentList "-NoExit", "-File", $tmp
    Write-Host "  Started: $Title" -ForegroundColor Cyan
}

$Base = @(
    "Set-Location '$Project'",
    "& '$CondaHook'",
    "conda activate txr_automation",
    "`$env:DATABASE_URL  = '$DbUrl'",
    "`$env:REDIS_URL     = '$RedisUrl'",
    "`$env:PYTHONPATH    = '$Project'",
    "`$env:DATA_DIR      = '$Project\data'",
    "`$env:UPLOAD_DIR    = 'data/uploads'",
    "`$env:FIRDS_DB_PATH = 'data/firds_cache.db'",
    "`$env:GLEIF_DB_PATH = 'data/gleif_cache.db'"
)

Write-Host ""
Write-Host "TXR Automation - Native Dev Startup" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Ensure Docker Desktop is running before touching any containers
# ---------------------------------------------------------------------------
Write-Host "Checking Docker Desktop..."
$dockerOk = $false
try { docker info 2>$null | Out-Null ; $dockerOk = $true } catch {}

if (-not $dockerOk) {
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Write-Host "  Docker Desktop not running - starting it..." -ForegroundColor Yellow
        Start-Process $dockerExe
        Write-Host "  Waiting for Docker daemon (up to 90 seconds)..." -ForegroundColor Yellow
        $waited = 0
        while ($waited -lt 90) {
            Start-Sleep -Seconds 5
            $waited += 5
            try { docker info 2>$null | Out-Null ; $dockerOk = $true ; break } catch {}
        }
    }
    if (-not $dockerOk) {
        Write-Host "  ERROR: Docker Desktop could not be started. Please start it manually and retry." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Docker Desktop is ready." -ForegroundColor Green
}

Write-Host "Starting backing services if needed..."

$rJson = docker compose ps redis --format json 2>$null
$dJson = docker compose ps db --format json 2>$null
$RedisOk = try { ($rJson | ConvertFrom-Json).State -eq "running" } catch { $false }
$DbOk    = try { ($dJson | ConvertFrom-Json).State -eq "running" } catch { $false }

if (-not $RedisOk -or -not $DbOk) {
    Write-Host "  Bringing up redis and db..." -ForegroundColor Yellow
    Push-Location $Project ; docker compose up -d redis db ; Pop-Location
    Start-Sleep -Seconds 3
}

Write-Host "Launching processes..."

Start-NativeWindow "API"    ($Base + @("uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"))
Start-NativeWindow "Worker" ($Base + @("celery -A api.tasks.celery_app worker --pool=threads --concurrency=4 --loglevel=info"))
Start-NativeWindow "Beat"   ($Base + @("celery -A api.tasks.celery_app beat --loglevel=info --schedule data/celery/celerybeat-schedule"))

$webTmp = Join-Path $env:TEMP "txr_Web.ps1"
"Set-Location '$(Join-Path $Project 'web')'", "npm run dev" | Set-Content -Path $webTmp -Encoding UTF8
Start-Process powershell -ArgumentList "-NoExit", "-File", $webTmp
Write-Host "  Started: Web (Vite HMR)" -ForegroundColor Cyan

Write-Host ""
Write-Host "Done. API -> http://localhost:8000 | Web -> http://localhost:5173" -ForegroundColor Green
