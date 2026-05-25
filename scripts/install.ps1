# Knowledge OS — global installer for Windows (PowerShell 5.1+)

$KOS_VERSION = "0.1.0"
$CONFIG_DIR = "$env:USERPROFILE\.k-os"
$CONFIG_FILE = "$CONFIG_DIR\config.yaml"

Write-Host "=== Knowledge OS Installer v$KOS_VERSION ===" -ForegroundColor Cyan

# Detect install path
if ($env:KOS_INSTALL_DIR) {
    $INSTALL_DIR = $env:KOS_INSTALL_DIR
} elseif (Test-Path "$PSScriptRoot\..\k-os") {
    $INSTALL_DIR = (Resolve-Path "$PSScriptRoot\..").Path
} else {
    Write-Host "Error: Run this from the KnowledgeSystem repo, or set KOS_INSTALL_DIR" -ForegroundColor Red
    exit 1
}

Write-Host "Install dir: $INSTALL_DIR"

# 1. Create global config directory
if (-not (Test-Path $CONFIG_DIR)) {
    New-Item -ItemType Directory -Path $CONFIG_DIR -Force | Out-Null
}

# 2. Write global config
if (-not (Test-Path $CONFIG_FILE)) {
    @"
install_dir: "$INSTALL_DIR"
default_vault: ""
databases:
  neo4j:
    uri: bolt://localhost:7687
    user: neo4j
    password: knowledge_os
  qdrant:
    host: localhost
    port: 6333
  opensearch:
    host: localhost
    port: 9200
"@ | Set-Content -Path $CONFIG_FILE -Encoding UTF8
    Write-Host "Created config: $CONFIG_FILE"
} else {
    $content = Get-Content $CONFIG_FILE -Raw
    $content = $content -replace 'install_dir:.*', "install_dir: `"$INSTALL_DIR`""
    Set-Content -Path $CONFIG_FILE -Value $content -Encoding UTF8
    Write-Host "Updated config: $CONFIG_FILE"
}

# 3. Add to PATH via k-os.cmd in a user-writable location
$BIN_DIR = "$CONFIG_DIR\bin"
if (-not (Test-Path $BIN_DIR)) {
    New-Item -ItemType Directory -Path $BIN_DIR -Force | Out-Null
}

$LAUNCHER = "$BIN_DIR\k-os.cmd"
@"
@echo off
REM Knowledge OS global launcher — installed by install.ps1
set INSTALL_DIR=$INSTALL_DIR
if exist "%INSTALL_DIR%\.venv\Scripts\python.exe" (
    "%INSTALL_DIR%\.venv\Scripts\python.exe" "%INSTALL_DIR%\k-os" %*
) else (
    python "%INSTALL_DIR%\k-os" %*
)
"@ | Set-Content -Path $LAUNCHER -Encoding ASCII
Write-Host "Installed launcher: $LAUNCHER"

# Add bin dir to user PATH if not already there
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BIN_DIR*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BIN_DIR", "User")
    $env:Path += ";$BIN_DIR"
    Write-Host "Added $BIN_DIR to user PATH"
}

# 4. Set up Claude Code slash command (global)
$CLAUDE_CMD_DIR = "$env:USERPROFILE\.claude\commands"
if (-not (Test-Path $CLAUDE_CMD_DIR)) {
    New-Item -ItemType Directory -Path $CLAUDE_CMD_DIR -Force | Out-Null
}

@"
# Knowledge OS Query

Run a knowledge query against the user's indexed vault using the Knowledge OS system.

Usage: /k-os <query>

Execute the query by running:
``````
k-os query "`$ARGUMENTS" -m claude --live
``````

If that fails (k-os not in PATH), try:
``````
python $INSTALL_DIR\k-os query "`$ARGUMENTS" -m claude --live
``````

Show the results to the user. If databases aren't running, suggest: ``docker compose -f $INSTALL_DIR\docker\docker-compose.yml up -d``
"@ | Set-Content -Path "$CLAUDE_CMD_DIR\k-os.md" -Encoding UTF8
Write-Host "Installed Claude Code command: /k-os"

# 5. Set up Python virtual environment if missing
if (-not (Test-Path "$INSTALL_DIR\.venv")) {
    Write-Host "Setting up Python venv..."
    python -m venv "$INSTALL_DIR\.venv"
    & "$INSTALL_DIR\.venv\Scripts\pip.exe" install -q pyyaml
    Write-Host "Virtual environment ready"
}

Write-Host ""
Write-Host "=== Installation complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Usage from any directory:"
Write-Host "  k-os -w C:\path\to\vault scan -v        # scan a vault"
Write-Host "  k-os -w C:\path\to\vault rebuild -v     # full rebuild"
Write-Host '  k-os query "your question" --live        # query knowledge'
Write-Host ""
Write-Host "In Claude Code (any directory):"
Write-Host "  /k-os what is cryptography"
Write-Host ""
Write-Host "Config: $CONFIG_FILE"
Write-Host ""
Write-Host "NOTE: Restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
