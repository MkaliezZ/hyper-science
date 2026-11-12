param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv-research\Scripts\python.exe'
if (-not $VerifyOnly) {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw '请先安装 uv，再执行本脚本。' }
    if (-not (Test-Path -LiteralPath $taskPython)) {
        & uv venv --python 3.12 (Join-Path $taskRoot '.venv-research')
        if ($LASTEXITCODE -ne 0) { throw '创建科研环境失败' }
    }
    & uv pip sync --python $taskPython (Join-Path $taskRoot 'requirements-research.lock')
    if ($LASTEXITCODE -ne 0) { throw '安装科研依赖失败' }
}
& $taskPython -I -c "import sys,simpy,numpy,pandas,pydoe,liteparse; print(sys.version); print('Scientific runtime imports: OK')"
if ($LASTEXITCODE -ne 0) { throw '科研执行环境校验失败' }
