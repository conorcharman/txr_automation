# Kill uvicorn (port 8000)
$api = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1
if ($api) { Stop-Process -Id $api -Force; Write-Host "  API (port 8000) stopped" -ForegroundColor Cyan }
else       { Write-Host "  API not running" -ForegroundColor Gray }

# Kill celery worker + beat
$celery = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'celery' }
if ($celery) {
    $celery | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "  Celery PID $($_.ProcessId) stopped" -ForegroundColor Cyan }
} else { Write-Host "  Celery not running" -ForegroundColor Gray }

# Kill vite dev server
$vite = Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -match 'vite' }
if ($vite) {
    $vite | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "  Vite PID $($_.ProcessId) stopped" -ForegroundColor Cyan }
} else { Write-Host "  Vite not running" -ForegroundColor Gray }

Write-Host ""
Write-Host "Done. Redis and PostgreSQL continue running in Docker." -ForegroundColor Green
