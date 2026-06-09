param(
    [string]$CondaEnv = "txr_automation",
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$AutoFormat
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Invoke-PythonModule {
    param(
        [string]$Module,
        [string[]]$Items
    )

    & python -m $Module $Items
    if ($LASTEXITCODE -ne 0) {
        throw "python -m $Module failed with exit code $LASTEXITCODE"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    if ($env:CONDA_DEFAULT_ENV -ne $CondaEnv) {
        $condaHook = Join-Path $env:USERPROFILE "AppData\Local\anaconda3\shell\condabin\conda-hook.ps1"
        if (-not (Test-Path $condaHook)) {
            throw "Conda hook not found at '$condaHook'. Activate '$CondaEnv' manually and re-run."
        }

        . $condaHook
        conda activate $CondaEnv
    }

    if (-not $SkipBackend) {
        if ($AutoFormat) {
            Invoke-Step "Format Python with black" { Invoke-PythonModule "black" @("src/", "tests/", "api/") }
            Invoke-Step "Sort imports with isort" {
                Invoke-PythonModule "isort" @("--profile", "black", "src/", "tests/", "api/")
            }
        }
        else {
            Invoke-Step "Check Python formatting with black" {
                Invoke-PythonModule "black" @("--check", "src/", "tests/", "api/")
            }
            Invoke-Step "Check Python imports with isort" {
                Invoke-PythonModule "isort" @("--profile", "black", "--check-only", "src/", "tests/", "api/")
            }
        }
        Invoke-Step "Lint with flake8" { Invoke-PythonModule "flake8" @("src/", "tests/", "api/") }
        Invoke-Step "Lint with pylint" { Invoke-PythonModule "pylint" @("src/", "api/") }
        Invoke-Step "Type-check API with mypy" {
            Invoke-PythonModule "mypy" @(
                "api/",
                "--ignore-missing-imports",
                "--disable-error-code",
                "import-untyped",
                "--disable-error-code",
                "attr-defined",
                "--disable-error-code",
                "arg-type"
            )
        }
        Invoke-Step "Run pytest with coverage" {
            Invoke-PythonModule "pytest" @("tests/", "--cov=src", "--cov-report=html", "--cov-report=term")
        }
    }

    if (-not $SkipFrontend) {
        Push-Location "web"
        try {
            Invoke-Step "Run frontend lint" { npm run lint }
        }
        finally {
            Pop-Location
        }
    }

    Write-Host "`nCode quality checks completed successfully." -ForegroundColor Green
}
finally {
    Pop-Location
}
