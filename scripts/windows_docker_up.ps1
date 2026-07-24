# Mount a Windows drive into Docker Desktop's WSL and start QuantPilot with a
# bind path Docker can see. Needed when Q-SEED lives on an exFAT / external drive
# (Docker Desktop's D:/... bind often appears empty).
#
# Requires: WSL 2 + Docker Desktop with WSL integration enabled.
#
# Usage (from repo root, PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows_docker_up.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows_docker_up.ps1 -HostDataPath "D:/path/to/Q-SEED/data"

param(
    [string]$HostDataPath = ""
)

$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

Write-Host "Preflight: checking WSL and Docker Desktop WSL backend..."
if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    throw "WSL is not available. Install WSL 2 and enable Docker Desktop WSL integration, then retry."
}
wsl -l -v | Out-Null
Assert-LastExitCode "wsl -l -v (is WSL installed and runnable?)"

docker version | Out-Null
Assert-LastExitCode "docker version (is Docker Desktop running with WSL backend?)"

docker info | Out-Null
Assert-LastExitCode "docker info (Docker engine not reachable — start Docker Desktop / enable WSL integration)"

if (-not $HostDataPath) {
    if (Test-Path ".env") {
        $line = Select-String -Path ".env" -Pattern "^\s*QSEED_HOST_PATH=(.+)$" | Select-Object -First 1
        if ($line) {
            $HostDataPath = $line.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
        }
    }
}

if (-not $HostDataPath) {
    throw "Set QSEED_HOST_PATH in .env or pass -HostDataPath"
}

# Normalize to D:/... then map to /mnt/d/...
$normalized = $HostDataPath -replace "\\", "/"
if ($normalized -notmatch "^([A-Za-z]):/(.*)$") {
    throw "HostDataPath must be a Windows drive path like D:/.... Got: $HostDataPath"
}
$drive = $Matches[1].ToLower()
$driveLetter = $Matches[1].ToUpper()
$rest = $Matches[2]
$mntPath = "/mnt/$drive/$rest"

Write-Host "Ensuring drive ${driveLetter}: is mounted in docker-desktop WSL..."
# Pass user path as positional args to a checked-in shell helper (not spliced into source).
$helperWin = Join-Path (Get-Location) "scripts\_windows_mount_qseed.sh"
if (-not (Test-Path $helperWin)) {
    throw "Missing helper script: $helperWin"
}
$wslHelper = (wsl -e wslpath -a $helperWin).Trim()
Assert-LastExitCode "wslpath for mount helper"
& wsl @("-u", "root", "-e", "sh", $wslHelper, $drive, $driveLetter, $mntPath)
Assert-LastExitCode "WSL drive mount / data dir check"

Write-Host "Starting Compose (bundled Ollama + quantpilot-dev) with QSEED_HOST_PATH=$mntPath"
$env:QSEED_HOST_PATH = $mntPath
docker compose --profile dev --profile bundled-ollama up -d --force-recreate ollama quantpilot-dev
if ($LASTEXITCODE -ne 0) {
    throw @"
docker compose up failed with exit code $LASTEXITCODE.
If the error mentions port 11434, stop the other process using that port (or an existing Ollama container) and retry.
Bundled flow expects both 'ollama' and 'quantpilot-dev' to start together.
"@
}

Write-Host "Verifying /data/qseed inside container..."
& docker @("compose", "exec", "-T", "quantpilot-dev", "sh", "/app/scripts/_windows_verify_qseed.sh")
Assert-LastExitCode "container /data/qseed verification"

Write-Host "Done. Bundled Ollama + quantpilot-dev are up. Example:"
Write-Host '  docker compose exec quantpilot-dev python scripts/run_agent_sim.py --start 2024-01-02 --target 12000000 --period-days 90 --hold-only'
