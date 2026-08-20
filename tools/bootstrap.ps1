$ErrorActionPreference = "Stop"

function Require-Command([string]$Name, [string]$Help) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing $Name. $Help"
    }
}

function Invoke-Checked([string]$Command, [string[]]$CommandArgs) {
    & $Command @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE."
    }
}

Require-Command "python" "Install Python 3.12 and add it to PATH."
Require-Command "uv" "Install uv from https://docs.astral.sh/uv/."
Require-Command "node" "Install Node.js 20 or newer."
Require-Command "npm" "Install npm with Node.js."

$pythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Python." }
if ($pythonVersion -ne "3.12") {
    throw "Python 3.12 is required; found $pythonVersion."
}
$uvVersionText = & uv --version
if ($LASTEXITCODE -ne 0 -or $uvVersionText -notmatch '(\d+\.\d+\.\d+)') {
    throw "Unable to inspect uv."
}
if ([version]$Matches[1] -lt [version]"0.9.0") {
    throw "uv 0.9 or newer is required; found $uvVersionText."
}
$nodeVersion = & node --version
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Node.js." }
$nodeMajor = [int]($nodeVersion.TrimStart("v").Split(".")[0])
if ($nodeMajor -lt 20) {
    throw "Node.js 20 or newer is required; found $nodeVersion."
}

if (-not (Test-Path -LiteralPath ".venv")) {
    Invoke-Checked "uv" @("venv", "--python", "3.12", ".venv")
}
Invoke-Checked "uv" @("sync", "--frozen", "--all-groups")
Push-Location "frontend"
try {
    Invoke-Checked "npm" @("ci")
} finally {
    Pop-Location
}

Write-Host "Compass dependencies are ready. No .env file was changed."
