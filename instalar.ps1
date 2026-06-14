<#
.SYNOPSIS
    Instalador do DarkSON - Assistente de Voz Inteligente
.DESCRIPTION
    Cria ambiente virtual, instala dependencias e cria atalhos no desktop e iniciar.
#>

$ErrorActionPreference = "Stop"
$DARKSON_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV_DIR = Join-Path $DARKSON_DIR "venv"
$DESKTOP = [Environment]::GetFolderPath("Desktop")
$START_MENU = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\DarkSON"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     DarkSON - Instalador" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar Python
try {
    $py = (Get-Command python).Source
    $ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Write-Host "[OK] Python $ver encontrado: $py" -ForegroundColor Green
} catch {
    Write-Host "[ERRO] Python nao encontrado. Instale Python 3.10+ de python.org" -ForegroundColor Red
    exit 1
}

# 2. Criar virtual environment
if (Test-Path $VENV_DIR) {
    Write-Host "[AVISO] Ambiente virtual ja existe. Pulando criacao." -ForegroundColor Yellow
} else {
    Write-Host "[...] Criando ambiente virtual..." -ForegroundColor Yellow
    & python -m venv $VENV_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERRO] Falha ao criar ambiente virtual" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Ambiente virtual criado" -ForegroundColor Green
}

# 3. Ativar e instalar dependencias
$pip = Join-Path $VENV_DIR "Scripts\pip.exe"
$python = Join-Path $VENV_DIR "Scripts\python.exe"

Write-Host "[...] Instalando dependencias (pode levar varios minutos)..." -ForegroundColor Yellow
& $pip install --upgrade pip -q
& $pip install -r (Join-Path $DARKSON_DIR "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERRO] Falha ao instalar dependencias" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Dependencias instaladas" -ForegroundColor Green

# 4. Verificar se .env existe, se nao criar padrao
$env_file = Join-Path $DARKSON_DIR ".env"
if (-not (Test-Path $env_file)) {
    @"
# DarkSON - Configuracao
AI_PROVIDER=ollama
OLLAMA_MODEL=minimax-m3:cloud
OLLAMA_URL=http://localhost:11434
USER_NAME=Fabricio
LANGUAGE=pt-BR
"@ | Set-Content -Path $env_file -Encoding UTF8
    Write-Host "[OK] .env padrao criado" -ForegroundColor Green
} else {
    Write-Host "[OK] .env ja existe" -ForegroundColor Green
}

# 5. Criar atalho no desktop
$bat_path = Join-Path $DESKTOP "DarkSON.bat"
Copy-Item (Join-Path $DARKSON_DIR "iniciar.bat") $bat_path -Force
Write-Host "[OK] Atalho criado no Desktop: $bat_path" -ForegroundColor Green

# 6. Criar atalho no iniciar
if (-not (Test-Path $START_MENU)) {
    New-Item -ItemType Directory -Path $START_MENU -Force | Out-Null
}
$start_bat = Join-Path $START_MENU "DarkSON.bat"
Copy-Item $bat_path $start_bat -Force
Write-Host "[OK] Atalho criado no Iniciar" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Instalacao concluida!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para iniciar o DarkSON:" -ForegroundColor White
Write-Host "  1. Dê um duplo clique em 'DarkSON.bat' no Desktop" -ForegroundColor Yellow
Write-Host "  2. Ou procure 'DarkSON' no Menu Iniciar" -ForegroundColor Yellow
Write-Host ""
Write-Host "O Edge vai abrir automaticamente em http://localhost:5000" -ForegroundColor White
Write-Host ""
Write-Host "IMPORTANTE: Certifique-se de que o Ollama esta rodando!" -ForegroundColor Magenta
Write-Host "  'ollama serve' no terminal ou execute o aplicativo Ollama." -ForegroundColor Magenta
Write-Host ""

pause
