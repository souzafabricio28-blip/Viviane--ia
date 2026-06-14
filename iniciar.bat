@echo off
title DarkSON
cd /d "%~dp0"

:: Ativa o venv se existir
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat" >nul 2>&1
)

:menu
cls
echo ================================================
echo          DarkSON - Assistente de Voz
echo ================================================
echo.
echo  [1] Voz      - modo comando de voz (console)
echo  [2] Desktop  - interface grafica customtkinter
echo  [3] Web      - servidor web (navegador)
echo  [4] Web/sil  - servidor web (sem janela)
echo.
echo  [I] Instalar dependencias
echo  [D] Desinstalar
echo  [S] Sair
echo.
echo ================================================
echo.

choice /c 1234IDS /n /m "Digite a opcao: "
if errorlevel 7 exit /b 0
if errorlevel 6 goto desinstalar
if errorlevel 5 goto instalar
if errorlevel 4 goto web_silencioso
if errorlevel 3 goto web
if errorlevel 2 goto desktop
if errorlevel 1 goto voz

:voz
cls
echo Iniciando DarkSON - Modo Voz...
echo Pressione Ctrl+C para encerrar
echo.
python main.py
pause
goto menu

:desktop
cls
echo Iniciando DarkSON - Interface Desktop...
echo.
python interface_darkson.py
pause
goto menu

:web
cls
echo Iniciando DarkSON - Servidor Web...
echo.
echo Abrindo Microsoft Edge...
start /min pythonw ui\run_server.py
timeout /t 4 /nobreak >nul
start msedge http://localhost:5000
echo Servidor rodando em http://localhost:5000
echo Pressione qualquer tecla para encerrar...
pause
if exist "data\web_server.pid" (
    for /f %%i in (data\web_server.pid) do taskkill /PID %%i /F 2>nul
) else (
    taskkill /f /im pythonw.exe 2>nul
)
goto menu

:web_silencioso
cls
echo Iniciando DarkSON - Servidor Web (silencioso)...
start /min pythonw ui\run_server.py
echo.
echo Servidor web iniciado em segundo plano.
echo Aguardando...
timeout /t 4 /nobreak >nul
echo Abrindo Microsoft Edge...
start msedge http://localhost:5000
echo.
echo Servidor rodando em http://localhost:5000
echo Pressione qualquer tecla para encerrar...
pause
if exist "data\web_server.pid" (
    for /f %%i in (data\web_server.pid) do taskkill /PID %%i /F 2>nul
) else (
    taskkill /f /im pythonw.exe 2>nul
)
goto menu

:instalar
cls
echo Instalando DarkSON...
echo.
if exist "venv" (
    echo Ambiente virtual ja existe. Recriando...
    rmdir /s /q venv
)
python -m venv venv
if errorlevel 1 (
    echo [ERRO] Falha ao criar ambiente virtual
    pause
    goto menu
)
call "venv\Scripts\activate.bat"
python -m pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias
    pause
    goto menu
)
if not exist ".env" (
    copy .env.example .env >nul
    echo [AVISO] Arquivo .env criado. Configure suas chaves de API.
)
echo.
echo Instalacao concluida!
pause
goto menu

:desinstalar
cls
echo Desinstalando DarkSON...
echo.
set /p "confirma=Tem certeza? (S/N): "
if /i not "%confirma%"=="S" goto menu
if exist "venv" (
    rmdir /s /q venv
    echo Ambiente virtual removido.
)
if exist "%USERPROFILE%\Desktop\DarkSON.bat" (
    del "%USERPROFILE%\Desktop\DarkSON.bat"
    echo Atalho do Desktop removido.
)
echo Desinstalacao concluida.
pause
goto menu
