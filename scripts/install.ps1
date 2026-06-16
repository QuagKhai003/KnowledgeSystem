# Knowledge OS - global installer for Windows (PowerShell 5.1+)

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
REM Knowledge OS global launcher - installed by install.ps1
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

# Track everything we touch so uninstall can reverse it cleanly
$script:MANIFEST_MCP = [System.Collections.ArrayList]::new()
$script:MANIFEST_FILES = [System.Collections.ArrayList]::new()

function Configure-MCP {
    param($Name, $ConfigFile, $KeyPath)

    $dir = Split-Path $ConfigFile -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    if (Test-Path $ConfigFile) {
        $raw = Get-Content $ConfigFile -Raw
        if ([string]::IsNullOrWhiteSpace($raw)) {
            $cfg = [PSCustomObject]@{}
        } else {
            $cfg = $raw | ConvertFrom-Json
        }
    } else {
        $cfg = [PSCustomObject]@{}
    }
    if ($null -eq $cfg) { $cfg = [PSCustomObject]@{} }

    $keys = $KeyPath -split '\.'
    $obj = $cfg
    for ($i = 0; $i -lt $keys.Count - 1; $i++) {
        $k = $keys[$i]
        $prop = $obj.PSObject.Properties[$k]
        if ($null -eq $prop -or $null -eq $prop.Value) {
            $child = [PSCustomObject]@{}
            if ($null -ne $prop) { $obj.PSObject.Properties.Remove($k) }
            $obj | Add-Member -NotePropertyName $k -NotePropertyValue $child
            $obj = $child
        } else {
            $obj = $obj.$k
        }
    }
    $lastKey = $keys[-1]
    if ($obj.PSObject.Properties.Name -contains $lastKey) {
        $obj.$lastKey = $MCP_ENTRY
    } else {
        $obj | Add-Member -NotePropertyName $lastKey -NotePropertyValue $MCP_ENTRY
    }

    $cfg | ConvertTo-Json -Depth 10 | Set-Content -Path $ConfigFile -Encoding UTF8
    [void]$script:MANIFEST_MCP.Add([PSCustomObject]@{ file = $ConfigFile; key_path = $KeyPath; format = "json" })
    Write-Host "  ${Name}: configured"
}

Write-Host "Configuring AI CLI integrations..."

# Claude Code - slash command
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
[void]$script:MANIFEST_FILES.Add("$CLAUDE_CMD_DIR\k-os.md")
Write-Host "  Claude Code: /k-os slash command installed"

# Claude Code - MCP server
if (Test-Path "$env:USERPROFILE\.claude") {
    Configure-MCP "Claude Code MCP" "$env:USERPROFILE\.claude\settings.json" "mcpServers.knowledge-os"
}

# Cursor - MCP server
if ((Test-Path "$env:USERPROFILE\.cursor") -or ($null -ne (Get-Command cursor -ErrorAction SilentlyContinue))) {
    Configure-MCP "Cursor" "$env:USERPROFILE\.cursor\mcp.json" "mcpServers.knowledge-os"
}

# Windsurf - MCP server
if ((Test-Path "$env:USERPROFILE\.codeium\windsurf") -or ($null -ne (Get-Command windsurf -ErrorAction SilentlyContinue))) {
    Configure-MCP "Windsurf" "$env:USERPROFILE\.codeium\windsurf\mcp_config.json" "mcpServers.knowledge-os"
}

# VS Code + Continue - MCP server
if (Test-Path "$env:USERPROFILE\.continue") {
    Configure-MCP "Continue" "$env:USERPROFILE\.continue\config.json" "mcpServers.knowledge-os"
}

# Codex CLI (OpenAI) - TOML config
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
        [void]$script:MANIFEST_MCP.Add([PSCustomObject]@{ file = $CODEX_CONFIG; key_path = "mcp_servers.knowledge-os"; format = "toml" })
        Write-Host "  Codex CLI: configured"
    } else {
        Write-Host "  Codex CLI: already configured"
    }
}

# Antigravity (Google/Gemini CLI) - MCP server
if ((Test-Path "$env:USERPROFILE\.gemini") -or ($null -ne (Get-Command antigravity -ErrorAction SilentlyContinue)) -or (Test-Path "$env:USERPROFILE\.antigravitycli")) {
    Configure-MCP "Antigravity" "$env:USERPROFILE\.gemini\config\mcp_config.json" "mcpServers.knowledge-os"
}

# 5. Set up Python virtual environment and install dependencies
if (-not (Test-Path "$INSTALL_DIR\.venv")) {
    Write-Host "Setting up Python venv..."
    python -m venv "$INSTALL_DIR\.venv"
}
Write-Host "Installing dependencies (this can take a few minutes; pip output below)..."
$pipPath = "$INSTALL_DIR\.venv\Scripts\pip.exe"
if (Test-Path "$INSTALL_DIR\requirements.txt") {
    & $pipPath install -r "$INSTALL_DIR\requirements.txt"
} else {
    & $pipPath install pyyaml
}
Write-Host "Virtual environment ready" -ForegroundColor Green

# 6. Optional: Docker databases for semantic search + graph traversal
# Decide whether the user wants the Docker tier. Honour $env:KOS_DOCKER for
# non-interactive installs (1/yes/true = on, 0/no/false = off); otherwise ask.
$wantDocker = $null
if ($env:KOS_DOCKER) {
    $wantDocker = $env:KOS_DOCKER -match '^(1|y|yes|true|on)$'
}

$dockerCli = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)

if ($null -eq $wantDocker) {
    Write-Host ""
    Write-Host "Knowledge OS has two tiers:" -ForegroundColor Cyan
    Write-Host "  Core (no Docker)  - keyword search, hubs, graph, auto-index. Works everywhere."
    Write-Host "  + Docker          - adds semantic vector search (Qdrant) and graph traversal (Neo4j)."
    if (-not $dockerCli) {
        Write-Host "  Docker was not found on PATH; choosing Yes will tell you how to add it later." -ForegroundColor Yellow
    }
    $answer = Read-Host "Install the Docker database tier? [y/N]"
    $wantDocker = $answer -match '^(y|yes)$'
}

$dockerActive = $false
if ($wantDocker) {
    Write-Host ""
    if (-not $dockerCli) {
        Write-Host "Docker not installed. Skipping container startup." -ForegroundColor Yellow
        Write-Host "  Install Docker Desktop, then run:"
        Write-Host "    docker compose -f $INSTALL_DIR\docker\docker-compose.yml up -d"
    } else {
        # Binary present != daemon running. Probe the daemon before compose.
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Docker is installed but the daemon is not running." -ForegroundColor Yellow
            Write-Host "  Start Docker Desktop, then run:"
            Write-Host "    docker compose -f $INSTALL_DIR\docker\docker-compose.yml up -d"
        } else {
            Write-Host "Starting databases (Qdrant + Neo4j)..."
            docker compose -f "$INSTALL_DIR\docker\docker-compose.yml" up -d
            Write-Host "Waiting for databases to be ready..."
            Start-Sleep -Seconds 15
            try { $null = Invoke-RestMethod -Uri "http://localhost:6333/healthz" -TimeoutSec 3; Write-Host "  Qdrant: ready" -ForegroundColor Green } catch { Write-Host "  Qdrant: not ready yet (wait ~30s)" -ForegroundColor Yellow }
            try { $null = Invoke-RestMethod -Uri "http://localhost:7474" -TimeoutSec 3; Write-Host "  Neo4j: ready" -ForegroundColor Green } catch { Write-Host "  Neo4j: not ready yet (wait ~30s)" -ForegroundColor Yellow }
            $dockerActive = $true
        }
    }
} else {
    Write-Host ""
    Write-Host "Core install (no Docker). Keyword search is fully enabled." -ForegroundColor Green
    Write-Host "  To add semantic search + graph traversal later, run:"
    Write-Host "    docker compose -f $INSTALL_DIR\docker\docker-compose.yml up -d"
}

# 7. Write the install manifest so `uninstall` can reverse everything in one command
$manifest = [PSCustomObject]@{
    version       = $KOS_VERSION
    installed_at  = (Get-Date).ToString("o")
    os            = "windows"
    kos_home      = $CONFIG_DIR
    config_file   = $CONFIG_FILE
    launcher      = $LAUNCHER
    path_entry    = $BIN_DIR
    claude_command = "$CLAUDE_CMD_DIR\k-os.md"
    docker        = [bool]$wantDocker
    compose_file  = "$INSTALL_DIR\docker\docker-compose.yml"
    files         = @($script:MANIFEST_FILES)
    mcp_edits     = @($script:MANIFEST_MCP)
}
$MANIFEST_FILE = "$CONFIG_DIR\install-manifest.json"
$manifest | ConvertTo-Json -Depth 10 | Set-Content -Path $MANIFEST_FILE -Encoding UTF8

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

if ($wantDocker) {
    Write-Host ""
    Write-Host "Docker tier - managing the databases:" -ForegroundColor Cyan
    Write-Host "  Start:  docker compose -f $INSTALL_DIR\docker\docker-compose.yml up -d"
    Write-Host "  Stop:   docker compose -f $INSTALL_DIR\docker\docker-compose.yml down"
    Write-Host "  Status: docker ps"
    Write-Host "  Qdrant UI: http://localhost:6333/dashboard   Neo4j UI: http://localhost:7474"
    if ($dockerActive) {
        Write-Host "  Containers are running now. Re-index a folder to populate them:"
    } else {
        Write-Host "  Start Docker Desktop, run the 'Start' command above, then re-index a folder:"
    }
    Write-Host "    k-os -w C:\path\to\vault rebuild -v"
}

Write-Host ""
Write-Host "Config:    $CONFIG_FILE"
Write-Host "Uninstall: irm https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/uninstall.ps1 | iex"
Write-Host ""
Write-Host "NOTE: Restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
