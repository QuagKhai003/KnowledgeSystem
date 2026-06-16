# Knowledge OS — one-command uninstaller for Windows (PowerShell 5.1+)
# Usage: irm https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/uninstall.ps1 | iex
#
# Reads the install manifest written at install time and reverses every change:
# Docker containers, MCP config entries, the Claude slash command, the launcher,
# the PATH entry, and the ~/.k-os directory. No manual cleanup required.

$ErrorActionPreference = "Continue"
$KOS_HOME = "$env:USERPROFILE\.k-os"
$MANIFEST_FILE = "$KOS_HOME\install-manifest.json"

Write-Host "=== Knowledge OS Uninstaller ===" -ForegroundColor Cyan

# Load the manifest, or fall back to known defaults if it is missing
if (Test-Path $MANIFEST_FILE) {
    $m = Get-Content $MANIFEST_FILE -Raw | ConvertFrom-Json
} else {
    Write-Host "No manifest found; using default locations." -ForegroundColor Yellow
    $m = [PSCustomObject]@{
        kos_home       = $KOS_HOME
        launcher       = "$KOS_HOME\bin\k-os.cmd"
        path_entry     = "$KOS_HOME\bin"
        claude_command = "$env:USERPROFILE\.claude\commands\k-os.md"
        compose_file   = "$KOS_HOME\KnowledgeSystem\docker\docker-compose.yml"
        docker         = $true
        files          = @()
        mcp_edits      = @()
    }
}

# 1. Stop and remove Docker containers (best effort; needs the compose file + daemon)
if ($m.docker -and $m.compose_file -and (Test-Path $m.compose_file)) {
    if ($null -ne (Get-Command docker -ErrorAction SilentlyContinue)) {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Stopping Docker databases..."
            docker compose -f $m.compose_file down -v 2>$null
        } else {
            Write-Host "Docker daemon not running; skipping container cleanup." -ForegroundColor Yellow
        }
    }
}

# 2. Remove our MCP entries from shared editor configs (leave other entries intact)
function Remove-JsonKeyPath {
    param($File, $KeyPath)
    if (-not (Test-Path $File)) { return }
    try { $cfg = Get-Content $File -Raw | ConvertFrom-Json } catch { return }
    if ($null -eq $cfg) { return }
    $keys = $KeyPath -split '\.'
    $obj = $cfg
    for ($i = 0; $i -lt $keys.Count - 1; $i++) {
        if ($null -eq $obj.PSObject.Properties[$keys[$i]]) { return }
        $obj = $obj.$($keys[$i])
        if ($null -eq $obj) { return }
    }
    $obj.PSObject.Properties.Remove($keys[-1])
    # Drop now-empty parent containers (e.g. an emptied mcpServers object)
    if ($keys.Count -ge 2) {
        $parent = $cfg
        for ($i = 0; $i -lt $keys.Count - 2; $i++) { $parent = $parent.$($keys[$i]) }
        $container = $parent.$($keys[$keys.Count - 2])
        if ($null -ne $container -and $container.PSObject.Properties.Count -eq 0) {
            $parent.PSObject.Properties.Remove($keys[$keys.Count - 2])
        }
    }
    $cfg | ConvertTo-Json -Depth 10 | Set-Content -Path $File -Encoding UTF8
}

function Remove-TomlSection {
    param($File, $Section)
    if (-not (Test-Path $File)) { return }
    $lines = Get-Content $File
    $out = New-Object System.Collections.Generic.List[string]
    $skip = $false
    foreach ($line in $lines) {
        if ($line -match '^\s*\[') {
            $skip = $line -match "^\s*\[$([regex]::Escape($Section))\]\s*$"
        }
        if (-not $skip) { $out.Add($line) }
    }
    ($out -join "`r`n").TrimEnd() | Set-Content -Path $File -Encoding UTF8
}

foreach ($edit in $m.mcp_edits) {
    if ($edit.format -eq "toml") {
        Remove-TomlSection $edit.file $edit.key_path
    } else {
        Remove-JsonKeyPath $edit.file $edit.key_path
    }
    Write-Host "  Cleaned MCP entry: $($edit.file)"
}

# 3. Remove standalone files we created (slash command, launcher, etc.)
$toDelete = @()
if ($m.claude_command) { $toDelete += $m.claude_command }
if ($m.launcher)       { $toDelete += $m.launcher }
if ($m.files)          { $toDelete += $m.files }
foreach ($f in $toDelete) {
    if ($f -and (Test-Path $f)) {
        Remove-Item -Force $f -ErrorAction SilentlyContinue
        Write-Host "  Removed: $f"
    }
}

# 4. Remove our bin dir from the user PATH
if ($m.path_entry) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath) {
        $newPath = ($userPath -split ';' | Where-Object { $_ -and $_ -ne $m.path_entry }) -join ';'
        if ($newPath -ne $userPath) {
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            Write-Host "  Removed from PATH: $($m.path_entry)"
        }
    }
}

# 5. Remove the entire Knowledge OS home (repo, venv, config, manifest)
if ($m.kos_home -and (Test-Path $m.kos_home)) {
    Remove-Item -Recurse -Force $m.kos_home -ErrorAction SilentlyContinue
    Write-Host "  Removed: $($m.kos_home)"
}

Write-Host ""
Write-Host "=== Knowledge OS uninstalled ===" -ForegroundColor Green
Write-Host "Restart your terminal to clear the PATH change." -ForegroundColor Yellow
