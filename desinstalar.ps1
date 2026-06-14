<#
.SYNOPSIS
    Desinstalador do DarkSON
#>

$ErrorActionPreference = "Stop"
$DARKSON_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV_DIR = Join-Path $DARKSON_DIR "venv"
$DESKTOP = [Environment]::GetFolderPath("Desktop")
$START_MENU = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\DarkSON"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   DarkSON - Desinstalador" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$resp = Read-Host "Tem certeza que deseja remover o DarkSON? (S/N)"
if ($resp -ne "S" -and $resp -ne "s") {
    Write-Host "Cancelado." -ForegroundColor Yellow
    exit
}

# Remover atalhos
$atalhos = @(
    (Join-Path $DESKTOP "DarkSON.bat"),
    (Join-Path $DESKTOP "DarkSON (rapido).bat"),
    (Join-Path $START_MENU "DarkSON.bat")
)
foreach ($a in $atalhos) {
    if (Test-Path $a) {
        Remove-Item $a -Force
        Write-Host "[OK] Removido: $a" -ForegroundColor Green
    }
}

# Remover pasta do iniciar
if (Test-Path $START_MENU) {
    Remove-Item $START_MENU -Recurse -Force -ErrorAction SilentlyContinue
}

# Remover venv
if (Test-Path $VENV_DIR) {
    Write-Host "[...] Removendo ambiente virtual..." -ForegroundColor Yellow
    Remove-Item $VENV_DIR -Recurse -Force
    Write-Host "[OK] Ambiente virtual removido" -ForegroundColor Green
}

Write-Host ""
Write-Host "DarkSON removido com sucesso." -ForegroundColor Green
Write-Host "Os arquivos do projeto em $DARKSON_DIR nao foram removidos." -ForegroundColor Yellow
Write-Host "Para remover completamente, apague a pasta manualmente." -ForegroundColor Yellow
Write-Host ""

pause
