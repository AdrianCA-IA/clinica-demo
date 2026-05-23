from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
from app.database import get_db
from app.models import Appointment
from app.schemas import AppointmentCreate, AppointmentOut
from core.availability import create_appointment_safe
from core.google_calendar import create_event_sync as create_event, cancel_event_sync as cancel_event, confirm_event_sync as confirm_event

router = APIRouter(prefix="/appointments", tags=["Citas"])


@router.post("/", response_model=AppointmentOut, summary="Crear cita (con validación de solapamiento)")
def create_appointment(data: AppointmentCreate, db: Session = Depends(get_db)):
    try:
        appointment = create_appointment_safe(
            patient_id=data.patient_id,
            doctor_id=data.doctor_id,
            appointment_type_id=data.appointment_type_id,
            start_datetime=data.start_datetime,
            notes=data.notes,
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Sincronizar con Google Calendar (no bloquea si falla)
    try:
        gcal_id = create_event(
            patient_name=appointment.patient.name,
            patient_phone=appointment.patient.phone,
            doctor_name=appointment.doctor.name,
            specialty=appointment.doctor.specialty,
            appointment_type=appointment.appointment_type.name,
            start_dt=appointment.start_datetime,
            end_dt=appointment.end_datetime,
            notes=appointment.notes,
        )
        if gcal_id:
            appointment.gcal_event_id = gcal_id
            db.commit()
            db.refresh(appointment)
    except Exception as e:
        import logging
        logging.getLogger("appointments").warning(f"⚠️ gcal sync error (cita guardada igualmente): {e}")

    return appointment


@router.get("/{appointment_id}", response_model=AppointmentOut, summary="Obtener cita por ID")
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    return appt


@router.patch("/{appointment_id}/cancel", response_model=AppointmentOut, summary="Cancelar cita")
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    if appt.status in ("cancelled", "completed"):
        raise HTTPException(status_code=400, detail=f"La cita ya está en estado '{appt.status}'")
    appt.status = "cancelled"
    db.commit()
    db.refresh(appt)

    # Marcar como cancelada en Google Calendar
    if appt.gcal_event_id:
        try:
            cancel_event(appt.gcal_event_id)
        except Exception as e:
            import logging
            logging.getLogger("appointments").warning(f"⚠️ gcal cancel error: {e}")

    return appt


@router.patch("/{appointment_id}/confirm", response_model=AppointmentOut, summary="Confirmar cita")
def confirm_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    if appt.status != "scheduled":
        raise HTTPException(status_code=400, detail=f"No se puede confirmar una cita en estado '{appt.status}'")
    appt.status = "confirmed"
    db.commit()
    db.refresh(appt)

    # Marcar como confirmada en Google Calendar (color azul)
    if appt.gcal_event_id:
        try:
            confirm_event(appt.gcal_event_id)
        except Exception as e:
            import logging
            logging.getLogger("appointments").warning(f"⚠️ gcal confirm error: {e}")

    return appt


@router.get("/", response_model=List[AppointmentOut], summary="Listar citas (filtrar por fecha, rango o doctor)")
def list_appointments(
    target_date: Optional[date] = Query(None, description="Filtrar por fecha exacta YYYY-MM-DD"),
    date_from: Optional[date] = Query(None, description="Rango inicio YYYY-MM-DD"),
    date_to: Optional[date] = Query(None, description="Rango fin YYYY-MM-DD"),
    doctor_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200, description="Máximo de resultados"),
    offset: int = Query(0, ge=0, description="Saltar N resultados (paginación)"),
    db: Session = Depends(get_db)
):
    query = db.query(Appointment)
    if target_date:
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date, datetime.max.time())
        query = query.filter(
            Appointment.start_datetime >= day_start,
            Appointment.start_datetime <= day_end
        )
    elif date_from and date_to:
        range_start = datetime.combine(date_from, datetime.min.time())
        range_end = datetime.combine(date_to, datetime.max.time())
        query = query.filter(
            Appointment.start_datetime >= range_start,
            Appointment.start_datetime <= range_end
        )
    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if status:
        query = query.filter(Appointment.status == status)
    return query.order_by(Appointment.start_datetime).offset(offset).limit(limit).all()
