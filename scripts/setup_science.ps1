param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$scienceRoot = Split-Path -Parent $PSScriptRoot
$sciencePython = Join-Path $scienceRoot '.venv-local\Scripts\python.exe'
if (-not $VerifyOnly) {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv before setup.' }
    if (-not (Test-Path -LiteralPath $sciencePython)) {
        & uv venv --python 3.11 (Join-Path $scienceRoot '.venv-local')
        if ($LASTEXITCODE -ne 0) { throw 'Host environment creation failed.' }
    }
    & uv pip sync --python $sciencePython (Join-Path $scienceRoot 'requirements-local.lock')
    if ($LASTEXITCODE -ne 0) { throw 'Host dependency installation failed.' }
    & (Join-Path $PSScriptRoot 'setup_research.ps1')
} else {
    & (Join-Path $PSScriptRoot 'setup_research.ps1') -VerifyOnly
}
if ($LASTEXITCODE -ne 0) { throw 'Research environment check failed.' }
& $sciencePython -c "import fastapi,uvicorn,mcp,keyring,aiortc,pydantic_ai; print('Host imports: OK')"
if ($LASTEXITCODE -ne 0) { throw 'Host import check failed.' }
