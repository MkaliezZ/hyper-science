param([int]$Port = 0, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$scienceRoot = Split-Path -Parent $PSScriptRoot
$sciencePython = Join-Path $scienceRoot '.venv-local\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $sciencePython)) { throw 'Run scripts/setup_science.ps1 first.' }
$scienceOldPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $scienceRoot 'src'
    $scienceArgs = @('-m','growth_local','--web','--data',(Join-Path $scienceRoot 'data\science'),'--port',"$Port")
    if ($NoBrowser) { $scienceArgs += '--no-browser' }
    & $sciencePython @scienceArgs
    if ($LASTEXITCODE -ne 0) { throw 'Hyper Science exited with an error.' }
} finally { $env:PYTHONPATH = $scienceOldPath }
