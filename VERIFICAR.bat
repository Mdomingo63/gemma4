@echo off
REM Script de verificación rápida - Proyecto Gemma4
REM Este archivo ayuda a diagnosticar el estado del proyecto

cls
echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║            VERIFICACION RAPIDA - PROYECTO GEMMA4                 ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.
echo [1] Verificando Python...
python --version 2>nul
if errorlevel 1 (
    echo ERROR: Python no encontrado en PATH
    goto END
) else (
    echo OK: Python encontrado
)

echo.
echo [2] Verificando Gradio...
python -c "import gradio; print('OK: Gradio ' + gradio.__version__)" 2>nul
if errorlevel 1 (
    echo ERROR: Gradio no está instalado
    echo Solución: pip install -r requirements.txt
    goto END
) else (
    echo OK: Gradio instalado
)

echo.
echo [3] Verificando Requests...
python -c "import requests; print('OK: Requests ' + requests.__version__)" 2>nul
if errorlevel 1 (
    echo ERROR: Requests no está instalado
    echo Solución: pip install -r requirements.txt
    goto END
) else (
    echo OK: Requests instalado
)

echo.
echo [4] Verificando sintaxis de app.py...
python -m py_compile app.py 2>nul
if errorlevel 1 (
    echo ERROR: Sintaxis inválida en app.py
    goto END
) else (
    echo OK: Sintaxis válida
)

echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║               VERIFICACION COMPLETADA - TODO OK                   ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.
echo Para ejecutar la aplicación:
echo.
echo   1. Abre 2 terminales (PowerShell o CMD)
echo.
echo   Terminal 1:
echo      ollama serve
echo.
echo   Terminal 2:
echo      python app.py
echo.
echo   Luego abre tu navegador en: http://localhost:7860
echo.

:END
pause
