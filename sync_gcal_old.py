"""
Sincroniza las citas antiguas (sin gcal_event_id) con Google Calendar.
Ejecutar UNA SOLA VEZ desde la carpeta del proyecto:
    python sync_gcal_old.py

Opciones:
    python sync_gcal_old.py --dry-run   → solo muestra qué haría, sin crear eventos
    python sync_gcal_old.py --delete    → elimina TODAS las citas de BD + Google Calendar y empieza de cero
"""
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("sync")

DRY_RUN = "--dry-run" in sys.argv
DELETE_ALL = "--delete" in sys.argv

# ── Conectar a la base de datos ────────────────────────────────────────────────

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

db_url = os.getenv("DATABASE_URL", "sqlite:///./clinica.db")
engine = create_engine(db_url, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
db = Session()

# ── Importar modelos (necesitan que Base ya esté creada) ──────────────────────

from app.models import Appointment, Patient, Doctor, AppointmentType
from app.database import Base
Base.metadata.create_all(bind=engine)

# ── Modo DELETE ALL ────────────────────────────────────────────────────────────

if DELETE_ALL:
    print("\n⚠️  MODO BORRADO TOTAL")
    print("Esto eliminará TODAS las citas de la BD y de Google Calendar.")
    confirm = input("Escribe CONFIRMAR para continuar: ").strip()
    if confirm != "CONFIRMAR":
        print("Cancelado.")
        sys.exit(0)

    from core.google_calendar import cancel_event_sync
    appointments = db.query(Appointment).all()
    deleted_gcal = 0
    deleted_db = 0

    for appt in appointments:
        if appt.gcal_event_id:
            try:
                cancel_event_sync(appt.gcal_event_id)
                deleted_gcal += 1
                log.info(f"  ❌ Google Calendar: evento {appt.gcal_event_id} marcado como cancelado")
            except Exception as e:
                log.warning(f"  ⚠️  No se pudo cancelar evento {appt.gcal_event_id}: {e}")
        db.delete(appt)
        deleted_db += 1

    db.commit()
    print(f"\n✅ Borradas {deleted_db} citas de la BD y {deleted_gcal} eventos de Google Calendar.")
    print("La BD está limpia. Ya puedes empezar de cero.")
    sys.exit(0)

# ── Modo SYNC ──────────────────────────────────────────────────────────────────

from core.google_calendar import create_event_sync

# Buscar citas sin gcal_event_id que no estén canceladas ni completadas
pending = db.query(Appointment).filter(
    Appointment.gcal_event_id == None,
    Appointment.status.in_(["scheduled", "confirmed"])
).order_by(Appointment.start_datetime).all()

print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Citas sin Google Calendar: {len(pending)}")
print("─" * 60)

if not pending:
    print("✅ Todas las citas ya están sincronizadas con Google Calendar.")
    sys.exit(0)

synced = 0
failed = 0

for appt in pending:
    patient_name = appt.patient.name if appt.patient else "Desconocido"
    patient_phone = appt.patient.phone if appt.patient else None
    doctor_name = appt.doctor.name if appt.doctor else "Desconocido"
    specialty = appt.doctor.specialty if appt.doctor else ""
    appt_type = appt.appointment_type.name if appt.appointment_type else "Consulta"
    start_dt = appt.start_datetime
    end_dt = appt.end_datetime

    label = f"ID:{appt.id} | {patient_name} | {doctor_name} | {appt_type} | {start_dt.strftime('%d/%m/%Y %H:%M')}"

    if DRY_RUN:
        print(f"  [DRY RUN] Crearía evento: {label}")
        synced += 1
        continue

    try:
        gcal_id = create_event_sync(
            patient_name=patient_name,
            patient_phone=patient_phone,
            doctor_name=doctor_name,
            specialty=specialty,
            appointment_type=appt_type,
            start_dt=start_dt,
            end_dt=end_dt,
            notes=appt.notes,
        )
        if gcal_id:
            appt.gcal_event_id = gcal_id
            db.commit()
            log.info(f"  ✅ {label} → {gcal_id}")
            synced += 1
        else:
            log.warning(f"  ⚠️  No se pudo crear evento para: {label} (Google Calendar no disponible)")
            failed += 1
    except Exception as e:
        log.error(f"  ❌ Error en cita ID:{appt.id}: {e}")
        failed += 1

print("─" * 60)
if DRY_RUN:
    print(f"[DRY RUN] Se crearían {synced} eventos en Google Calendar.")
else:
    print(f"✅ Sincronizadas: {synced}  |  ❌ Fallidas: {failed}")
    if failed == 0:
        print("Google Calendar está completamente al día.")
    else:
        print("Comprueba los errores arriba. ¿Está configurado GOOGLE_REFRESH_TOKEN en .env?")

db.close()
