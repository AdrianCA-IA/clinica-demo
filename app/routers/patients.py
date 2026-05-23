from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Patient
from app.schemas import PatientCreate, PatientOut

router = APIRouter(prefix="/patients", tags=["Pacientes"])


@router.post("/", response_model=PatientOut, summary="Crear paciente")
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    existing = db.query(Patient).filter(Patient.phone == patient.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un paciente con ese teléfono")
    db_patient = Patient(**patient.model_dump())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


@router.get("/phone/{phone}", response_model=PatientOut, summary="Buscar paciente por teléfono")
def get_patient_by_phone(phone: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.phone == phone).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return patient


@router.get("/{patient_id}", response_model=PatientOut, summary="Obtener paciente por ID")
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return patient
