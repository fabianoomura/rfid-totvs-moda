@echo off
echo ============================================================
echo RFID Middleware Simulator - MOOUI
echo ============================================================
echo.
echo Iniciando interface grafica...
echo.

python rfid_middleware_gui.py

if %errorlevel% neq 0 (
    echo.
    echo ERRO: Falha ao iniciar a GUI
    echo.
    echo Verifique se o Python esta instalado:
    echo   python --version
    echo.
    echo Verifique se as dependencias estao instaladas:
    echo   pip install -r requirements_simulator.txt
    echo.
    pause
)
