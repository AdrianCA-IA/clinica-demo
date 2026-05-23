from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app.models import Doctor, AppointmentType
from app.schemas import AvailabilityResponse, TimeSlot
from core.availability import check_availability

router = APIRouter(prefix="/availability", tags=["Disponibilidad"])


@router.get(
    "/doctor/{doctor_id}",
    response_model=AvailabilityResponse,
    summary="Ver huecos disponibles de un doctor en una fecha"
)
def get_doctor_availability(
    doctor_id: int,
    appointment_type_id: int = Query(..., description="ID del tipo de cita"),
    target_date: date = Query(..., description="Fecha en formato YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    doctor = db.get(Doctor, doctor_id)
    if not doctor or not doctor.active:
        raise HTTPException(status_code=404, detail="Doctor no encontrado")

    appt_type = db.get(AppointmentType, appointment_type_id)
    if not appt_type:
        raise HTTPException(status_code=404, detail="Tipo de cita no encontrado")

    slots = check_availability(doctor_id, appointment_type_id, target_date, db)

    return AvailabilityResponse(
        doctor_id=doctor.id,
        doctor_name=doctor.name,
        date=str(target_date),
        appointment_type=appt_type.name,
        duration_minutes=appt_type.duration_minutes,
        available_slots=[TimeSlot(start=s["start"], end=s["end"]) for s in slots]
    )
