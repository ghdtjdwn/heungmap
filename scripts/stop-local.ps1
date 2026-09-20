[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RuntimeRoot = Join-Path $env:TEMP "heungmap-local"
$StatePath = Join-Path $RuntimeRoot "processes.json"

if (-not (Test-Path -LiteralPath $StatePath)) {
    Write-Host "저장된 로컬 실행 정보가 없습니다."
    exit 0
}

$state = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json
$targets = @(
    @{ Name = "frontend"; Port = [int]$state.frontend_port; ProcessId = [int]$state.frontend_pid },
    @{ Name = "backend"; Port = [int]$state.backend_port; ProcessId = [int]$state.backend_pid }
)

foreach ($target in $targets) {
    $listener = Get-NetTCPConnection -LocalPort $target.Port -State Listen -ErrorAction SilentlyContinue |
        Where-Object { [int]$_.OwningProcess -eq $target.ProcessId } |
        Select-Object -First 1
    if ($listener) {
        Stop-Process -Id $target.ProcessId -Force
        Write-Host "$($target.Name)를 종료했습니다. (PID $($target.ProcessId))"
    } else {
        Write-Host "$($target.Name)는 이미 종료됐거나 다른 프로세스로 바뀌었습니다."
    }
}

Remove-Item -LiteralPath $StatePath -Force
