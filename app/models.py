from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Time
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Patient(Base):
    """Paciente de la clínica."""
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointments = relationship("Appointment", back_populates="patient")


class Doctor(Base):
    """Doctor de la clínica."""
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    specialty = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    active = Column(Boolean, default=True)

    availability_rules = relationship("AvailabilityRule", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")


class AppointmentType(Base):
    """Tipo de cita con su duración en minutos."""
    __tablename__ = "appointment_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    description = Column(String, nullable=True)

    appointments = relationship("Appointment", back_populates="appointment_type")


class AvailabilityRule(Base):
    """Horario de trabajo de un doctor para un día de la semana.
    weekday: 0=Lunes, 1=Martes, ..., 6=Domingo
    """
    __tablename__ = "availability_rules"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    weekday = Column(Integer, nullable=False)   # 0=Lun ... 6=Dom
    start_time = Column(String, nullable=False)  # "09:00"
    end_time = Column(String, nullable=False)    # "14:00"
    active = Column(Boolean, default=True)

    doctor = relationship("Doctor", back_populates="availability_rules")


class Appointment(Base):
    """Cita médica."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    appointment_type_id = Column(Integer, ForeignKey("appointment_types.id"), nullable=False)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    # Estado: scheduled | confirmed | cancelled | completed
    status = Column(String, default="scheduled", nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    gcal_event_id = Column(String, nullable=True)  # ID del evento en Google Calendar

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    appointment_type = relationship("AppointmentType", back_populates="appointments")
