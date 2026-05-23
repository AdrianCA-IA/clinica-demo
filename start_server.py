"""
Arranca el servidor de la clínica demo.
Doble clic en este archivo para ejecutarlo.
"""
import subprocess
import sys
import os

# Moverse al directorio del script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("  Clinica Demo - Sistema de Citas con IA")
print("=" * 50)

# 1. Instalar dependencias
print("\n[1/3] Instalando dependencias...")
subprocess.check_call([
    sys.executable, "-m", "pip", "install",
    "fastapi", "uvicorn[standard]", "sqlalchemy",
    "pydantic", "python-dateutil", "-q"
])
print("    OK")

# 2. Seed de datos
print("\n[2/3] Poblando base de datos con datos de demo...")
try:
    from app.database import Base, engine
    Base.metadata.create_all(bind=engine)
    from seed_data import run_seed
    run_seed()
except Exception as e:
    print(f"    Aviso: {e} (puede que ya existan datos)")

# 3. Arrancar servidor
print("\n[3/3] Arrancando servidor...")
print("\n  Abre en tu navegador: http://localhost:8000/docs\n")

import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
