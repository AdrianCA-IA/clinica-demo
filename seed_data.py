"""
Script para poblar la base de datos con datos de demo.
Ejecutar: python seed_data.py
O llamar al endpoint: POST /seed
"""

from datetime import datetime, timedelta, date
from app.database import SessionLocal, engine, Base
from app.models import Patient, Doctor, AppointmentType, AvailabilityRule, Appointment


def run_seed(db=None):
    """Popula la BD con datos de demo. Si se pasa una sesión, la usa; si no, crea una."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Limpiar tablas en orden correcto (por FK)
        db.query(Appointment).delete()
        db.query(AvailabilityRule).delete()
        db.query(Patient).delete()
        db.query(AppointmentType).delete()
        db.query(Doctor).delete()
        db.commit()

        # ── Tipos de cita ─────────────────────────────────────────────────
        tipos = [
            AppointmentType(name="Revisión general",     duration_minutes=30,  description="Revisión rutinaria"),
            AppointmentType(name="Limpieza dental",      duration_minutes=45,  description="Higiene bucal profesional"),
            AppointmentType(name="Extracción",           duration_minutes=60,  description="Extracción simple o compleja"),
            AppointmentType(name="Consulta ortodoncia",  duration_minutes=45,  description="Valoración o seguimiento ortodoncia"),
            AppointmentType(name="Implante",             duration_minutes=90,  description="Colocación de implante dental"),
        ]
        db.add_all(tipos)
        db.commit()
        for t in tipos:
            db.refresh(t)

        # ── Doctores ──────────────────────────────────────────────────────
        garcia   = Doctor(name="Dr. García",   specialty="Odontología general", phone="600111222", active=True)
        lopez    = Doctor(name="Dra. López",   specialty="Ortodoncia",          phone="600333444", active=True)
        martinez = Doctor(name="Dr. Martínez", specialty="Implantología",       phone="600555666", active=True)
        db.add_all([garcia, lopez, martinez])
        db.commit()
        for d in [garcia, lopez, martinez]:
            db.refresh(d)

        # ── Reglas de disponibilidad ──────────────────────────────────────
        # Dr. García: Lun-Vie mañana (9-14) y tarde (16-19)
        garcia_rules = []
        for weekday in range(5):  # 0=Lun ... 4=Vie
            garcia_rules.append(AvailabilityRule(doctor_id=garcia.id, weekday=weekday, start_time="09:00", end_time="14:00"))
            garcia_rules.append(AvailabilityRule(doctor_id=garcia.id, weekday=weekday, start_time="16:00", end_time="19:00"))

        # Dra. López: Mar-Jue (1,2,3) de 10:00 a 15:00
        lopez_rules = [
            AvailabilityRule(doctor_id=lopez.id, weekday=1, start_time="10:00", end_time="15:00"),
            AvailabilityRule(doctor_id=lopez.id, weekday=2, start_time="10:00", end_time="15:00"),
            AvailabilityRule(doctor_id=lopez.id, weekday=3, start_time="10:00", end_time="15:00"),
        ]

        # Dr. Martínez: Lun/Mié/Vie (0,2,4) de 9:00 a 13:00
        martinez_rules = [
            AvailabilityRule(doctor_id=martinez.id, weekday=0, start_time="09:00", end_time="13:00"),
            AvailabilityRule(doctor_id=martinez.id, weekday=2, start_time="09:00", end_time="13:00"),
            AvailabilityRule(doctor_id=martinez.id, weekday=4, start_time="09:00", end_time="13:00"),
        ]

        db.add_all(garcia_rules + lopez_rules + martinez_rules)
        db.commit()

        # ── Pacientes ─────────────────────────────────────────────────────
        p1 = Patient(name="Ana Martínez",   phone="612345678", email="ana@example.com")
        p2 = Patient(name="Carlos Ruiz",    phone="698765432", email="carlos@example.com")
        p3 = Patient(name="María González", phone="655555555", email="maria@example.com")
        db.add_all([p1, p2, p3])
        db.commit()
        for p in [p1, p2, p3]:
            db.refresh(p)

        # ── Citas de demo (próximos 7 días hábiles) ───────────────────────
        # Encontrar el próximo lunes para tener días limpios
        today = date.today()
        days_ahead = (7 - today.weekday()) % 7  # días hasta el próximo lunes
        if days_ahead == 0:
            days_ahead = 7
        next_monday = today + timedelta(days=days_ahead)

        # Revisión con García el lunes a las 9:00
        appt1_start = datetime.combine(next_monday, datetime.strptime("09:00", "%H:%M").time())
        appt1 = Appointment(
            patient_id=p1.id, doctor_id=garcia.id,
            appointment_type_id=tipos[0].id,  # Revisión 30min
            start_datetime=appt1_start,
            end_datetime=appt1_start + timedelta(minutes=30),
            status="confirmed", notes="Primera visita"
        )

        # Limpieza con García el lunes a las 10:00
        appt2_start = datetime.combine(next_monday, datetime.strptime("10:00", "%H:%M").time())
        appt2 = Appointment(
            patient_id=p2.id, doctor_id=garcia.id,
            appointment_type_id=tipos[1].id,  # Limpieza 45min
            start_datetime=appt2_start,
            end_datetime=appt2_start + timedelta(minutes=45),
            status="scheduled"
        )

        # Consulta ortodoncia con López el martes a las 11:00
        next_tuesday = next_monday + timedelta(days=1)
        appt3_start = datetime.combine(next_tuesday, datetime.strptime("11:00", "%H:%M").time())
        appt3 = Appointment(
            patient_id=p3.id, doctor_id=lopez.id,
            appointment_type_id=tipos[3].id,  # Ortodoncia 45min
            start_datetime=appt3_start,
            end_datetime=appt3_start + timedelta(minutes=45),
            status="scheduled"
        )

        # Implante con Martínez el miércoles a las 09:00
        next_wednesday = next_monday + timedelta(days=2)
        appt4_start = datetime.combine(next_wednesday, datetime.strptime("09:00", "%H:%M").time())
        appt4 = Appointment(
            patient_id=p1.id, doctor_id=martinez.id,
            appointment_type_id=tipos[4].id,  # Implante 90min
            start_datetime=appt4_start,
            end_datetime=appt4_start + timedelta(minutes=90),
            status="confirmed", notes="Segunda fase del implante"
        )

        # Extracción con García el viernes a las 16:00 (turno tarde)
        next_friday = next_monday + timedelta(days=4)
        appt5_start = datetime.combine(next_friday, datetime.strptime("16:00", "%H:%M").time())
        appt5 = Appointment(
            patient_id=p2.id, doctor_id=garcia.id,
            appointment_type_id=tipos[2].id,  # Extracción 60min
            start_datetime=appt5_start,
            end_datetime=appt5_start + timedelta(minutes=60),
            status="scheduled"
        )

        db.add_all([appt1, appt2, appt3, appt4, appt5])
        db.commit()

        print("✅ Base de datos poblada con datos de demo:")
        print(f"   - 3 doctores")
        print(f"   - 5 tipos de cita")
        print(f"   - 3 pacientes")
        print(f"   - 5 citas (semana del {next_monday})")

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    run_seed()
