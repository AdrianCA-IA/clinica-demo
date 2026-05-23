from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


# ─── Patient ────────────────────────────────────────────────────────────────

class PatientCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None

class PatientOut(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Doctor ─────────────────────────────────────────────────────────────────

class DoctorOut(BaseModel):
    id: int
    name: str
    specialty: str
    active: bool

    model_config = {"from_attributes": True}


# ─── AppointmentType ────────────────────────────────────────────────────────

class AppointmentTypeOut(BaseModel):
    id: int
    name: str
    duration_minutes: int
    description: Optional[str]

    model_config = {"from_attributes": True}


# ─── Appointment ────────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_type_id: int
    start_datetime: datetime
    notes: Optional[str] = None

class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_type_id: int
    start_datetime: datetime
    end_datetime: datetime
    status: str
    notes: Optional[str]
    created_at: datetime
    gcal_event_id: Optional[str] = None
    patient: PatientOut
    doctor: DoctorOut
    appointment_type: AppointmentTypeOut

    model_config = {"from_attributes": True}


# ─── Availability ───────────────────────────────────────────────────────────

class TimeSlot(BaseModel):
    start: str   # "09:00"
    end: str     # "09:30"

class AvailabilityResponse(BaseModel):
    doctor_id: int
    doctor_name: str
    date: str
    appointment_type: str
    duration_minutes: int
    available_slots: List[TimeSlot]
