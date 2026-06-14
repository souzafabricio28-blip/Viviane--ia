@echo off
title DarkSON - Instalador
cd /d "%~dp0"

echo ========================================
echo     DarkSON - Instalador
echo ========================================
echo.
echo Verificando requisitos...

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Python nao encontrado. Instale Python 3.10+ de python.org
    pause
    exit /b 1
)

python --version

echo.
echo Criando ambiente virtual...
if exist "venv" (
    echo [AVISO] Ambiente virtual ja existe.
) else (
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo [ERRO] Falha ao criar ambiente virtual
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado
)

echo.
echo Instalando dependencias (pode levar varios minutos)...
call "venv\Scripts\pip.exe" install --upgrade pip -q
call "venv\Scripts\pip.exe" install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Falha ao instalar dependencias
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas

if not exist ".env" (
    echo AI_PROVIDER=ollama> .env
    echo OLLAMA_MODEL=minimax-m3:cloud>> .env
    echo OLLAMA_URL=http://localhost:11434>> .env
    echo USER_NAME=Fabricio>> .env
    echo LANGUAGE=pt-BR>> .env
    echo [OK] .env padrao criado
) else (
    echo [OK] .env ja existe
)

echo.
echo Criando atalho no Desktop...
set "DESKTOP=%USERPROFILE%\Desktop"
copy /Y "iniciar.bat" "%DESKTOP%\DarkSON.bat" >nul
echo [OK] Atalho criado: %%DESKTOP%%\DarkSON.bat

echo.
echo ========================================
echo  Instalacao concluida!
echo ========================================
echo.
echo Para iniciar o DarkSON:
echo   1. De um duplo clique em 'DarkSON.bat' no Desktop
echo   2. Ou execute 'rodar_darkson.bat' nesta pasta
echo.
echo IMPORTANTE: Certifique-se de que o Ollama esta rodando!
echo   Execute 'ollama serve' no terminal antes de iniciar.
echo.
pause
