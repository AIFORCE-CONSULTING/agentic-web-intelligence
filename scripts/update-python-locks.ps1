[CmdletBinding()]
param(
    [ValidateSet("all", "api", "docs")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonImage = "python:3.12-slim"
$pipToolsVersion = "7.4.1"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required to generate Python lockfiles."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running. Start it, then run this command again."
}

function Invoke-PipCompile {
    param(
        [Parameter(Mandatory)]
        [string]$Workdir,
        [Parameter(Mandatory)]
        [string]$CompileArguments
    )

    $containerCommand = @(
        "python -m pip install --disable-pip-version-check --no-cache-dir pip-tools==$pipToolsVersion",
        "python -m piptools compile $CompileArguments"
    ) -join " && "

    docker run --rm --mount "type=bind,source=$repoRoot,target=/workspace" --workdir $Workdir $pythonImage sh -c $containerCommand
    if ($LASTEXITCODE -ne 0) {
        throw "pip-compile failed for $Workdir."
    }
}

if ($Target -in @("all", "api")) {
    Invoke-PipCompile "/workspace/apps/api" "--generate-hashes --output-file=requirements.lock pyproject.toml"
    Invoke-PipCompile "/workspace/apps/api" "--extra=dev --generate-hashes --output-file=requirements-dev.lock pyproject.toml"
}

if ($Target -in @("all", "docs")) {
    Invoke-PipCompile "/workspace" "--generate-hashes --output-file=docs/requirements.lock docs/requirements.in"
}

Write-Host "Lockfile generation completed. Review the diff, then run:"
Write-Host "  python scripts/check_python_lock_consistency.py"
