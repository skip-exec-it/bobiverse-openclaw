# fleet-sync.ps1 — Mirror shared skills into local workspace (Windows)
# Schedule via Task Scheduler every 30 minutes

param(
    [string]$ClawdbotHome = $env:CLAWDBOT_HOME,
    [string]$Workspace    = "$env:USERPROFILE\.openclaw\workspace"
)

if (-not $ClawdbotHome) {
    Write-Error "CLAWDBOT_HOME is not set. Set the environment variable or pass -ClawdbotHome."
    exit 1
}

$SkillsSrc  = Join-Path $ClawdbotHome "skills"
$SkillsDst  = Join-Path $Workspace    "skills"
$SharedSrc  = Join-Path $ClawdbotHome "shared"
$LogFile    = Join-Path $Workspace    "fleet-sync.log"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts fleet-sync: $msg" | Tee-Object -FilePath $LogFile -Append | Write-Host
}

New-Item -ItemType Directory -Force -Path $SkillsDst | Out-Null

Log "starting"

# Mirror skills
if (Test-Path $SkillsSrc) {
    robocopy $SkillsSrc $SkillsDst /MIR /XD "__pycache__" "node_modules" /XF "*.pyc" /NP /NFL /NDL /NJH /NJS | Out-Null
    Log "skills synced"
} else {
    Log "WARN skills source not found: $SkillsSrc"
}

# Mirror shared docs
if (Test-Path $SharedSrc) {
    robocopy $SharedSrc $Workspace /E /XF "waiver-register.csv" /NP /NFL /NDL /NJH /NJS | Out-Null
    Log "shared docs synced"
}

Log "done"
