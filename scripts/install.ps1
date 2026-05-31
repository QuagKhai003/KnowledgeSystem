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

# 4. Configure AI CLI integrations
$PYTHON_BIN = "$INSTALL_DIR\.venv\Scripts\python.exe"
$MCP_SCRIPT = "$INSTALL_DIR\src\mcp_server.py"
$MCP_ENTRY = @{ command = $PYTHON_BIN; args = @($MCP_SCRIPT) }

function Configure-MCP {
    param($Name, $ConfigFile, $KeyPath)

    $dir = Split-Path $ConfigFile -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    if (Test-Path $ConfigFile) {
        $cfg = Get-Content $ConfigFile -Raw | ConvertFrom-Json
    } else {
        $cfg = [PSCustomObject]@{}
    }

    $keys = $KeyPath -split '\.'
    $obj = $cfg
    for ($i = 0; $i -lt $keys.Count - 1; $i++) {
        $k = $keys[$i]
        if (-not ($obj.PSObject.Properties.Name -contains $k)) {
            $obj | Add-Member -NotePropertyName $k -NotePropertyValue ([PSCustomObject]@{})
        }
        $obj = $obj.$k
    }
    $lastKey = $keys[-1]
    if ($obj.PSObject.Properties.Name -contains $lastKey) {
        $obj.$lastKey = $MCP_ENTRY
    } else {
        $obj | Add-Member -NotePropertyName $lastKey -NotePropertyValue $MCP_ENTRY
    }

    $cfg | ConvertTo-Json -Depth 10 | Set-Content -Path $ConfigFile -Encoding UTF8
    Write-Host "  ${Name}: configured"
}

Write-Host "Configuring AI CLI integrations..."

# Claude Code — slash command
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
k-os query "`$ARGUMENTS" --live
``````

If that fails (k-os not in PATH), try:
``````
python $INSTALL_DIR\k-os query "`$ARGUMENTS" --live
``````

Show the results to the user. If databases aren't running, suggest: ``docker compose -f $INSTALL_DIR\docker\docker-compose.yml up -d``
"@ | Set-Content -Path "$CLAUDE_CMD_DIR\k-os.md" -Encoding UTF8
Write-Host "  Claude Code: /k-os slash command installed"

# Claude Code — MCP server
if (Test-Path "$env:USERPROFILE\.claude") {
    Configure-MCP "Claude Code MCP" "$env:USERPROFILE\.claude\settings.json" "mcpServers.knowledge-os"
}

# Cursor — MCP server
if ((Test-Path "$env:USERPROFILE\.cursor") -or ($null -ne (Get-Command cursor -ErrorAction SilentlyContinue))) {
    Configure-MCP "Cursor" "$env:USERPROFILE\.cursor\mcp.json" "mcpServers.knowledge-os"
}

# Windsurf — MCP server
if ((Test-Path "$env:USERPROFILE\.codeium\windsurf") -or ($null -ne (Get-Command windsurf -ErrorAction SilentlyContinue))) {
    Configure-MCP "Windsurf" "$env:USERPROFILE\.codeium\windsurf\mcp_config.json" "mcpServers.knowledge-os"
}

# VS Code + Continue — MCP server
if (Test-Path "$env:USERPROFILE\.continue") {
    Configure-MCP "Continue" "$env:USERPROFILE\.continue\config.json" "mcpServers.knowledge-os"
}

# Codex CLI (OpenAI) — TOML config
$CODEX_CONFIG = "$env:USERPROFILE\.codex\config.toml"
if ((Test-Path "$env:USERPROFILE\.codex") -or ($null -ne (Get-Command codex -ErrorAction SilentlyContinue))) {
    if (-not (Test-Path "$env:USERPROFILE\.codex")) {
        New-Item -ItemType Directory -Path "$env:USERPROFILE\.codex" -Force | Out-Null
    }
    $codexContent = ""
    if (Test-Path $CODEX_CONFIG) {
        $codexContent = Get-Content $CODEX_CONFIG -Raw
    }
    if ($codexContent -notlike "*mcp_servers.knowledge-os*") {
        $tomlBlock = @"

[mcp_servers.knowledge-os]
enabled = true
command = "$PYTHON_BIN"
args = ["$MCP_SCRIPT"]
"@
        Add-Content -Path $CODEX_CONFIG -Value $tomlBlock
        Write-Host "  Codex CLI: configured"
    } else {
        Write-Host "  Codex CLI: already configured"
    }
}

# Antigravity (Google/Gemini CLI) — MCP server
if ((Test-Path "$env:USERPROFILE\.gemini") -or ($null -ne (Get-Command antigravity -ErrorAction SilentlyContinue)) -or (Test-Path "$env:USERPROFILE\.antigravitycli")) {
    Configure-MCP "Antigravity" "$env:USERPROFILE\.gemini\config\mcp_config.json" "mcpServers.knowledge-os"
}

# 5. Set up Python virtual environment and install dependencies
if (-not (Test-Path "$INSTALL_DIR\.venv")) {
    Write-Host "Setting up Python venv..."
    python -m venv "$INSTALL_DIR\.venv"
}
Write-Host "Installing dependencies..."
$pipPath = "$INSTALL_DIR\.venv\Scripts\pip.exe"
if (Test-Path "$INSTALL_DIR\requirements.txt") {
    & $pipPath install -q -r "$INSTALL_DIR\requirements.txt" 2>$null
} else {
    & $pipPath install -q pyyaml
}
Write-Host "Virtual environment ready"

# 6. Optional: Docker databases for semantic search + graph traversal
if ($null -ne (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "Docker found. Starting optional databases (Qdrant + Neo4j)..."
    docker compose -f "$INSTALL_DIR\docker\docker-compose.yml" up -d
    Write-Host "Waiting for databases to be ready..."
    Start-Sleep -Seconds 15

    # Health checks
    try { $null = Invoke-RestMethod -Uri "http://localhost:6333/healthz" -TimeoutSec 3; Write-Host "  Qdrant: ready" } catch { Write-Host "  Qdrant: not ready yet (wait ~30s)" }
    try { $null = Invoke-RestMethod -Uri "http://localhost:7474" -TimeoutSec 3; Write-Host "  Neo4j: ready" } catch { Write-Host "  Neo4j: not ready yet (wait ~30s)" }
} else {
    Write-Host ""
    Write-Host "Docker not found - skipping optional databases." -ForegroundColor Yellow
    Write-Host "  k-os works fully with keyword search (SQLite FTS5, built-in)."
    Write-Host "  For semantic search + graph traversal, install Docker and run:"
    Write-Host "    docker compose -f $INSTALL_DIR\docker\docker-compose.yml up -d"
}

Write-Host ""
Write-Host "=== Installation complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Usage from any directory:"
Write-Host "  k-os -w C:\path\to\vault rebuild -v     # index a vault"
Write-Host '  k-os query "your question" --live        # query knowledge'
Write-Host ""
Write-Host "In any AI CLI:"
Write-Host "  Claude Code:   /k-os what is cryptography"
Write-Host "  Cursor:        uses k-os tools automatically (MCP)"
Write-Host "  Windsurf:      uses k-os tools automatically (MCP)"
Write-Host "  Continue:      uses k-os tools automatically (MCP)"
Write-Host "  Codex CLI:     uses k-os tools automatically (MCP)"
Write-Host "  Antigravity:   uses k-os tools automatically (MCP)"
Write-Host ""
Write-Host "Config: $CONFIG_FILE"
Write-Host ""
Write-Host "NOTE: Restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
