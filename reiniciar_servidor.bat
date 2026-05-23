@echo off
echo ============================================
echo  Reiniciando servidor Clinica Demo
echo ============================================

REM Matar cualquier proceso uvicorn existente
echo Deteniendo uvicorn anterior...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq uvicorn*" 2>nul
taskkill /F /IM uvicorn.exe 2>nul

REM Ir a la carpeta del proyecto
cd /d "%~dp0"
echo.
echo Carpeta: %CD%
echo.

REM Activar entorno virtual si existe (ajusta el path si lo tienes en otro lado)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo Entorno virtual activado.
)

REM Arrancar uvicorn (sin --reload para evitar reinicios por cambios de archivos)
echo Arrancando uvicorn...
echo.
uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
