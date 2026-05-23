@echo off
echo ============================================
echo  Clinica Demo - Sistema de Citas con IA
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Instalando dependencias...
pip install fastapi "uvicorn[standard]" sqlalchemy pydantic python-dateutil -q
if errorlevel 1 (
    echo ERROR instalando dependencias. Asegurate de tener Python y pip instalados.
    pause
    exit /b 1
)

echo [2/3] Creando base de datos con datos de demo...
python seed_data.py

echo.
echo [3/3] Arrancando servidor...
echo.
echo  Abre en tu navegador: http://localhost:8000/docs
echo.
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
