"""
REGLA DE ORO: Este módulo es el único que toca la lógica de agenda.
El LLM (agente IA) NUNCA escribe en la BD directamente.
Solo puede llamar las funciones de este módulo.
"""

from datetime import datetime, timedelta, date
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Doctor, AvailabilityRule, Appointment, AppointmentType


SLOT_STEP_MINUTES = 15  # granularidad de los huecos disponibles


def _time_str_to_obj(time_str: str) -> datetime:
    """Convierte '09:30' a un objeto time."""
    return datetime.strptime(time_str, "%H:%M").time()


def check_availability(
    doctor_id: int,
    appointment_type_id: int,
    target_date: date,
    db: Session
) -> List[dict]:
    """
    Devuelve la lista de huecos disponibles para un doctor en una fecha dada.
    Tiene en cuenta:
    - Reglas de horario del doctor (AvailabilityRule)
    - Citas ya existentes (status: scheduled o confirmed)
    - Duración del tipo de cita

    Retorna lista de dicts: [{"start": "09:00", "end": "09:30"}, ...]
    """
    weekday = target_date.weekday()  # 0=Lun ... 6=Dom

    # 1. Obtener reglas de disponibilidad del doctor para ese día
    rules = db.query(AvailabilityRule).filter(
        AvailabilityRule.doctor_id == doctor_id,
        AvailabilityRule.weekday == weekday,
        AvailabilityRule.active == True
    ).all()

    if not rules:
        return []  # el doctor no trabaja ese día

    # 2. Obtener duración del tipo de cita
    appt_type = db.get(AppointmentType, appointment_type_id)
    if not appt_type:
        return []
    duration = timedelta(minutes=appt_type.duration_minutes)

    # 3. Obtener citas existentes de ese doctor en esa fecha
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    existing = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.start_datetime >= day_start,
        Appointment.start_datetime < day_end,
        Appointment.status.in_(["scheduled", "confirmed"])
    ).all()

    busy_intervals = [(a.start_datetime, a.end_datetime) for a in existing]

    # 4. Generar todos los huecos posibles dentro de cada regla de horario
    available = []
    for rule in rules:
        start_time = _time_str_to_obj(rule.start_time)
        end_time = _time_str_to_obj(rule.end_time)

        slot_start = datetime.combine(target_date, start_time)
        work_end = datetime.combine(target_date, end_time)

        while slot_start + duration <= work_end:
            slot_end = slot_start + duration

            # Comprobar que el hueco no solapa con ninguna cita existente
            overlaps = any(
                slot_start < busy_end and slot_end > busy_start
                for busy_start, busy_end in busy_intervals
            )

            if not overlaps:
                available.append({
                    "start": slot_start.strftime("%H:%M"),
                    "end": slot_end.strftime("%H:%M")
                })

            slot_start += timedelta(minutes=SLOT_STEP_MINUTES)

    return available


def create_appointment_safe(
    patient_id: int,
    doctor_id: int,
    appointment_type_id: int,
    start_datetime: datetime,
    notes: Optional[str],
    db: Session
) -> Appointment:
    """
    Crea una cita validando que no haya solapamiento.
    Lanza ValueError si el hueco no está disponible.
    Esta función es la única puerta de entrada para crear citas.
    """
    appt_type = db.get(AppointmentType, appointment_type_id)
    if not appt_type:
        raise ValueError(f"Tipo de cita {appointment_type_id} no existe")

    end_datetime = start_datetime + timedelta(minutes=appt_type.duration_minutes)

    # Verificar solapamiento con citas existentes del doctor
    conflict = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status.in_(["scheduled", "confirmed"]),
        Appointment.start_datetime < end_datetime,
        Appointment.end_datetime > start_datetime
    ).first()

    if conflict:
        raise ValueError(
            f"El hueco {start_datetime.strftime('%H:%M')} – {end_datetime.strftime('%H:%M')} "
            f"ya está ocupado (cita #{conflict.id})"
        )

    # Verificar que el horario cae dentro de las reglas del doctor
    target_date = start_datetime.date()
    slots = check_availability(doctor_id, appointment_type_id, target_date, db)
    requested_start = start_datetime.strftime("%H:%M")
    valid_slot = any(s["start"] == requested_start for s in slots)

    if not valid_slot:
        raise ValueError(
            f"El horario {requested_start} no es válido para este doctor en esa fecha"
        )

    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        appointment_type_id=appointment_type_id,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        status="scheduled",
        notes=notes
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment
