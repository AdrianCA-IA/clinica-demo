from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Doctor, AppointmentType
from app.schemas import DoctorOut, AppointmentTypeOut

router = APIRouter(prefix="/doctors", tags=["Doctores"])


@router.get("/", response_model=List[DoctorOut], summary="Listar todos los doctores activos")
def list_doctors(db: Session = Depends(get_db)):
    return db.query(Doctor).filter(Doctor.active == True).all()


@router.get("/appointment-types", response_model=List[AppointmentTypeOut], summary="Listar tipos de cita")
def list_appointment_types(db: Session = Depends(get_db)):
    return db.query(AppointmentType).all()
