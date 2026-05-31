# Knowledge OS — one-line installer for Windows
# Usage: irm https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.ps1 | iex

$KOS_HOME = "$env:USERPROFILE\.k-os"
$KOS_REPO = "$KOS_HOME\KnowledgeSystem"
$REPO_URL = "https://github.com/QuagKhai003/KnowledgeSystem.git"

Write-Host "=== Knowledge OS Bootstrap ===" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
if ($null -eq (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: git is required. Install git first." -ForegroundColor Red
    exit 1
}

if ($null -eq (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: python is required. Install Python 3.11+ first." -ForegroundColor Red
    exit 1
}

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "NOTE: Docker not found - optional databases (semantic search, graph) will be skipped." -ForegroundColor Yellow
    Write-Host "  k-os works fully with keyword search (SQLite FTS5, built-in)."
    Write-Host "  To add semantic search later, install Docker and run:"
    Write-Host "    docker compose -f $KOS_HOME\KnowledgeSystem\docker\docker-compose.yml up -d"
    Write-Host ""
}

# Clone or update repo
if (Test-Path $KOS_REPO) {
    Write-Host "Updating existing installation..."
    git -C $KOS_REPO pull --quiet
} else {
    Write-Host "Downloading Knowledge OS..."
    if (-not (Test-Path $KOS_HOME)) {
        New-Item -ItemType Directory -Path $KOS_HOME -Force | Out-Null
    }
    git clone --quiet $REPO_URL $KOS_REPO
}

# Run the full install script
Write-Host ""
$env:KOS_INSTALL_DIR = $KOS_REPO
& powershell -ExecutionPolicy Bypass -File "$KOS_REPO\scripts\install.ps1"
