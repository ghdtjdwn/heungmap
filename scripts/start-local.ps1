[CmdletBinding()]
param(
    [int]$FrontendPort = 3000,
    [int]$BackendPort = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RuntimeRoot = Join-Path $env:TEMP "heungmap-local"
$StatePath = Join-Path $RuntimeRoot "processes.json"
$BackendOut = Join-Path $RuntimeRoot "backend.out.log"
$BackendErr = Join-Path $RuntimeRoot "backend.err.log"
$FrontendOut = Join-Path $RuntimeRoot "frontend.out.log"
$FrontendErr = Join-Path $RuntimeRoot "frontend.err.log"
$FrontendUrl = "http://127.0.0.1:$FrontendPort"
$BackendUrl = "http://127.0.0.1:$BackendPort"

# 로컬 실행은 개발용 체험 로그인과 loopback origin으로 고정한다.
$env:HEUNGMAP_ENV = "development"
$env:HEUNGMAP_AUTH_MODE = "mock"
$env:HEUNGMAP_PUBLIC_ORIGIN = $FrontendUrl
$env:HEUNGMAP_BACKEND_URL = $BackendUrl

function Get-ListeningProcessId([int]$Port) {
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($connection) { return [int]$connection.OwningProcess }
    return $null
}

function Wait-ForHttp([string]$Url, [int]$Seconds = 60) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python 가상환경이 없습니다. 저장소 루트에서 python -m venv .venv 후 요구사항을 설치하세요."
}
if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
    throw "frontend/node_modules가 없습니다. frontend 폴더에서 npm install을 먼저 실행하세요."
}

$Npm = (Get-Command npm.cmd -ErrorAction Stop).Source
New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null

$backendPid = Get-ListeningProcessId $BackendPort
if ($backendPid) {
    try {
        $health = Invoke-RestMethod -Uri "$BackendUrl/api/v1/health" -TimeoutSec 3
        if ($health.service -ne "heungmap-api") { throw "unexpected service" }
        Write-Host "백엔드가 이미 실행 중입니다. (PID $backendPid)"
    } catch {
        throw "$BackendPort 포트를 다른 프로그램이 사용 중입니다. 해당 프로그램을 종료하거나 -BackendPort를 변경하세요."
    }
} else {
    $backendProcess = Start-Process -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "$BackendPort") `
        -WorkingDirectory $ProjectRoot -WindowStyle Hidden `
        -RedirectStandardOutput $BackendOut -RedirectStandardError $BackendErr -PassThru
    Write-Host "백엔드를 시작했습니다. (launcher PID $($backendProcess.Id))"
}

$frontendPid = Get-ListeningProcessId $FrontendPort
if ($frontendPid) {
    try {
        $page = Invoke-WebRequest -UseBasicParsing -Uri $FrontendUrl -TimeoutSec 3
        if ($page.Content -notmatch "흥할지도|HeungMap") { throw "unexpected service" }
        Write-Host "프론트엔드가 이미 실행 중입니다. (PID $frontendPid)"
    } catch {
        throw "$FrontendPort 포트를 다른 프로그램이 사용 중입니다. 해당 프로그램을 종료하거나 -FrontendPort를 변경하세요."
    }
} else {
    $frontendProcess = Start-Process -FilePath $Npm `
        -ArgumentList @("run", "dev", "--", "--hostname", "127.0.0.1", "--port", "$FrontendPort") `
        -WorkingDirectory $FrontendRoot -WindowStyle Hidden `
        -RedirectStandardOutput $FrontendOut -RedirectStandardError $FrontendErr -PassThru
    Write-Host "프론트엔드를 시작했습니다. (launcher PID $($frontendProcess.Id))"
}

if (-not (Wait-ForHttp "$BackendUrl/api/v1/health")) {
    throw "백엔드가 준비되지 않았습니다. 로그를 확인하세요: $BackendErr"
}
if (-not (Wait-ForHttp $FrontendUrl)) {
    throw "프론트엔드가 준비되지 않았습니다. 로그를 확인하세요: $FrontendErr"
}

$backendPid = Get-ListeningProcessId $BackendPort
$frontendPid = Get-ListeningProcessId $FrontendPort
@{
    project_root = $ProjectRoot
    backend_port = $BackendPort
    backend_pid = $backendPid
    frontend_port = $FrontendPort
    frontend_pid = $frontendPid
    started_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding utf8

$model = Invoke-RestMethod -Uri "$BackendUrl/api/v1/system/model-status" -TimeoutSec 10
Write-Host ""
Write-Host "흥할지도 로컬 실행 준비 완료"
Write-Host "화면: $FrontendUrl"
Write-Host "API:  $BackendUrl"
Write-Host "모델: $($model.status) / $($model.model_version)"
Write-Host "로그: $RuntimeRoot"
Write-Host "종료: .\scripts\stop-local.ps1"

if (-not $NoBrowser) {
    Start-Process $FrontendUrl
}
