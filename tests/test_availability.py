"""
Tests unitarios para core/availability.py
Usan una BD SQLite en memoria — sin servidor, sin dependencias externas.
"""
import pytest
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Doctor, AppointmentType, AvailabilityRule, Appointment, Patient
from core.availability import check_availability, create_appointment_safe


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Base de datos en memoria para cada test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def base_data(db):
    """Crea datos mínimos: 1 doctor, 1 tipo de cita, 1 paciente, regla de lunes."""
    doctor = Doctor(name="Dr. Test", specialty="General", active=True)
    db.add(doctor)

    atype = AppointmentType(name="Revisión", duration_minutes=30, active=True)
    db.add(atype)

    patient = Patient(name="Paciente Test", phone="600000000")
    db.add(patient)

    db.flush()

    # Lunes (weekday=0), 09:00–13:00
    rule = AvailabilityRule(
        doctor_id=doctor.id,
        weekday=0,
        start_time="09:00",
        end_time="13:00",
        active=True
    )
    db.add(rule)
    db.commit()

    return {"doctor": doctor, "atype": atype, "patient": patient, "rule": rule}


# ── Próximo lunes helper ─────────────────────────────────────────────────────────

def next_monday():
    today = date.today()
    days_ahead = (7 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


# ── Tests de disponibilidad ──────────────────────────────────────────────────────

class TestCheckAvailability:

    def test_slots_returned_on_working_day(self, db, base_data):
        """El doctor trabaja el lunes — debe devolver huecos."""
        doctor = base_data["doctor"]
        atype  = base_data["atype"]
        monday = next_monday()

        slots = check_availability(doctor.id, atype.id, monday, db)
        assert len(slots) > 0

    def test_no_slots_on_non_working_day(self, db, base_data):
        """El doctor no tiene regla para domingo — no debe haber huecos."""
        doctor = base_data["doctor"]
        atype  = base_data["atype"]

        # Buscar el próximo domingo
        today = date.today()
        days_ahead = (6 - today.weekday()) % 7 or 7
        sunday = today + timedelta(days=days_ahead)

        slots = check_availability(doctor.id, atype.id, sunday, db)
        assert slots == []

    def test_slot_duration_matches_appointment_type(self, db, base_data):
        """Cada hueco debe tener la duración del tipo de cita (30 min)."""
        doctor = base_data["doctor"]
        atype  = base_data["atype"]
        monday = next_monday()

        slots = check_availability(doctor.id, atype.id, monday, db)
        assert len(slots) > 0

        first = slots[0]
        start = datetime.strptime(first["start"], "%H:%M")
        end   = datetime.strptime(first["end"],   "%H:%M")
        assert (end - start).seconds == 30 * 60

    def test_slot_within_working_hours(self, db, base_data):
        """Todos los huecos deben estar dentro del horario 09:00–13:00."""
        doctor = base_data["doctor"]
        atype  = base_data["atype"]
        monday = next_monday()

        slots = check_availability(doctor.id, atype.id, monday, db)
        for slot in slots:
            start = datetime.strptime(slot["start"], "%H:%M").time()
            end   = datetime.strptime(slot["end"],   "%H:%M").time()
            assert start >= datetime.strptime("09:00", "%H:%M").time()
            assert end   <= datetime.strptime("13:00", "%H:%M").time()

    def test_booked_slot_not_returned(self, db, base_data):
        """Un hueco ya reservado no debe aparecer en la disponibilidad."""
        doctor  = base_data["doctor"]
        atype   = base_data["atype"]
        patient = base_data["patient"]
        monday  = next_monday()

        # Reservar 09:00–09:30
        dt_start = datetime.combine(monday, datetime.strptime("09:00", "%H:%M").time())
        dt_end   = datetime.combine(monday, datetime.strptime("09:30", "%H:%M").time())
        appt = Appointment(
            patient_id=patient.id, doctor_id=doctor.id,
            appointment_type_id=atype.id,
            start_datetime=dt_start, end_datetime=dt_end,
            status="scheduled"
        )
        db.add(appt)
        db.commit()

        slots = check_availability(doctor.id, atype.id, monday, db)
        slot_starts = [s["start"] for s in slots]
        assert "09:00" not in slot_starts

    def test_cancelled_appointment_frees_slot(self, db, base_data):
        """Una cita cancelada debe liberar el hueco."""
        doctor  = base_data["doctor"]
        atype   = base_data["atype"]
        patient = base_data["patient"]
        monday  = next_monday()

        dt_start = datetime.combine(monday, datetime.strptime("09:00", "%H:%M").time())
        dt_end   = datetime.combine(monday, datetime.strptime("09:30", "%H:%M").time())
        appt = Appointment(
            patient_id=patient.id, doctor_id=doctor.id,
            appointment_type_id=atype.id,
            start_datetime=dt_start, end_datetime=dt_end,
            status="cancelled"
        )
        db.add(appt)
        db.commit()

        slots = check_availability(doctor.id, atype.id, monday, db)
        slot_starts = [s["start"] for s in slots]
        assert "09:00" in slot_starts


# ── Tests de creación de citas ───────────────────────────────────────────────────

class TestCreateAppointmentSafe:

    def test_creates_appointment_successfully(self, db, base_data):
        """Crear una cita en un hueco libre debe funcionar."""
        doctor  = base_data["doctor"]
        atype   = base_data["atype"]
        patient = base_data["patient"]
        monday  = next_monday()

        dt_start = datetime.combine(monday, datetime.strptime("10:00", "%H:%M").time())
        appt = create_appointment_safe(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_type_id=atype.id,
            start_datetime=dt_start,
            notes="Test",
            db=db
        )
        assert appt.id is not None
        assert appt.status == "scheduled"
        assert appt.patient_id == patient.id
        assert appt.doctor_id == doctor.id

    def test_raises_on_overlap(self, db, base_data):
        """Crear dos citas solapadas debe lanzar ValueError."""
        doctor  = base_data["doctor"]
        atype   = base_data["atype"]
        patient = base_data["patient"]
        monday  = next_monday()

        dt_start = datetime.combine(monday, datetime.strptime("10:00", "%H:%M").time())

        # Primera cita — OK
        create_appointment_safe(patient.id, doctor.id, atype.id, dt_start, None, db)

        # Segunda en el mismo hueco — debe fallar
        with pytest.raises(ValueError, match="solapamiento|conflicto|no disponible"):
            create_appointment_safe(patient.id, doctor.id, atype.id, dt_start, None, db)

    def test_end_datetime_calculated_correctly(self, db, base_data):
        """La hora de fin debe ser inicio + duración del tipo de cita."""
        doctor  = base_data["doctor"]
        atype   = base_data["atype"]  # 30 minutos
        patient = base_data["patient"]
        monday  = next_monday()

        dt_start = datetime.combine(monday, datetime.strptime("09:00", "%H:%M").time())
        appt = create_appointment_safe(patient.id, doctor.id, atype.id, dt_start, None, db)

        expected_end = dt_start + timedelta(minutes=30)
        assert appt.end_datetime == expected_end

    def test_two_doctors_can_have_same_slot(self, db, base_data):
        """Dos doctores distintos pueden tener citas al mismo tiempo."""
        atype   = base_data["atype"]
        patient = base_data["patient"]
        monday  = next_monday()

        # Segundo doctor con misma regla de horario
        doctor2 = Doctor(name="Dr. Segundo", specialty="Ortodoncia", active=True)
        db.add(doctor2)
        db.flush()
        rule2 = AvailabilityRule(
            doctor_id=doctor2.id, weekday=0,
            start_time="09:00", end_time="13:00", active=True
        )
        db.add(rule2)
        db.commit()

        dt_start = datetime.combine(monday, datetime.strptime("10:00", "%H:%M").time())

        appt1 = create_appointment_safe(patient.id, base_data["doctor"].id, atype.id, dt_start, None, db)
        appt2 = create_appointment_safe(patient.id, doctor2.id, atype.id, dt_start, None, db)

        assert appt1.id != appt2.id
        assert appt1.doctor_id != appt2.doctor_id
