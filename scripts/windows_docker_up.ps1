# Mount Windows D: into Docker Desktop's WSL and start QuantPilot with a bind
# path Docker can see. Needed when Q-SEED lives on an exFAT / external drive
# (Docker Desktop's D:/... bind often appears empty).
#
# Usage (from repo root, PowerShell):
#   .\scripts\windows_docker_up.ps1
#   .\scripts\windows_docker_up.ps1 -HostDataPath "D:/path/to/Q-SEED/data"

param(
    [string]$HostDataPath = ""
)

$ErrorActionPreference = "Stop"

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
$rest = $Matches[2]
$mntPath = "/mnt/$drive/$rest"

Write-Host "Ensuring drive $($drive.ToUpper()): is mounted in docker-desktop WSL..."
wsl -u root -e sh -c "mkdir -p /mnt/$drive; mountpoint -q /mnt/$drive || mount -t drvfs $($drive.ToUpper()): /mnt/$drive; test -d '$mntPath' || (echo 'Missing data dir: $mntPath' >&2; exit 1); ls '$mntPath' | head -3"

Write-Host "Starting Compose with QSEED_HOST_PATH=$mntPath"
$env:QSEED_HOST_PATH = $mntPath
docker compose --profile dev --profile bundled-ollama up -d --force-recreate quantpilot-dev

Write-Host "Verifying /data/qseed inside container..."
docker compose exec quantpilot-dev sh -c "ls /data/qseed | head -5; ls /data/qseed | wc -l"

Write-Host "Done. Example:"
Write-Host '  docker compose exec quantpilot-dev python scripts/run_agent_sim.py --start 2024-01-02 --target 12000000 --period-days 90 --hold-only'
