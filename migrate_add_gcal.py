"""
Migración: añade columna gcal_event_id a la tabla appointments si no existe.
Ejecutar UNA VEZ después de actualizar el código.

Uso:
    python migrate_add_gcal.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "clinica.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print("ℹ️  No existe clinica.db — se creará sola al arrancar el servidor.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ver columnas actuales
    cursor.execute("PRAGMA table_info(appointments)")
    columns = [row[1] for row in cursor.fetchall()]

    if "gcal_event_id" in columns:
        print("✅ La columna gcal_event_id ya existe — nada que hacer.")
    else:
        cursor.execute("ALTER TABLE appointments ADD COLUMN gcal_event_id TEXT")
        conn.commit()
        print("✅ Columna gcal_event_id añadida correctamente a appointments.")

    conn.close()

if __name__ == "__main__":
    migrate()
