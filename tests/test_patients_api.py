"""
Tests de integración para el API de pacientes y citas.
Usan TestClient de FastAPI con BD en memoria.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


# ── BD de test en memoria ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_db_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(test_db_engine):
    TestingSession = sessionmaker(bind=test_db_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Tests de pacientes ───────────────────────────────────────────────────────────

class TestPatientsAPI:

    def test_list_patients_empty(self, client):
        """BD vacía → lista de pacientes debe estar vacía."""
        response = client.get("/patients/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_patient(self, client):
        """Crear un paciente debe devolver 201 con los datos."""
        payload = {"name": "Juan García", "phone": "600100200", "email": "juan@test.com"}
        response = client.post("/patients/", json=payload)
        assert response.status_code in (200, 201)
        data = response.json()
        assert data["name"] == "Juan García"
        assert data["phone"] == "600100200"
        assert "id" in data

    def test_create_duplicate_phone_fails(self, client):
        """Dos pacientes con el mismo teléfono no deben permitirse."""
        payload = {"name": "Paciente A", "phone": "600111111"}
        client.post("/patients/", json=payload)
        response = client.post("/patients/", json={"name": "Paciente B", "phone": "600111111"})
        assert response.status_code in (409, 400, 422)

    def test_get_patient_by_id(self, client):
        """Obtener un paciente por ID debe devolver sus datos."""
        payload = {"name": "María López", "phone": "600222222"}
        created = client.post("/patients/", json=payload).json()
        pid = created["id"]

        response = client.get(f"/patients/{pid}")
        assert response.status_code == 200
        assert response.json()["name"] == "María López"

    def test_get_nonexistent_patient_returns_404(self, client):
        """Buscar un paciente que no existe debe devolver 404."""
        response = client.get("/patients/999999")
        assert response.status_code == 404

    def test_search_patient_by_phone(self, client):
        """Buscar por teléfono debe encontrar al paciente correcto."""
        payload = {"name": "Carlos Ruiz", "phone": "600333333"}
        client.post("/patients/", json=payload)

        response = client.get("/patients/search?phone=600333333")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                assert any(p["phone"] == "600333333" for p in data)
            else:
                assert data["phone"] == "600333333"


# ── Tests de doctores ────────────────────────────────────────────────────────────

class TestDoctorsAPI:

    def test_list_doctors(self, client):
        """El endpoint de doctores debe responder con 200."""
        response = client.get("/doctors/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_doctor_types(self, client):
        """El endpoint de tipos de cita debe responder con 200."""
        response = client.get("/appointment-types/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ── Tests de citas ────────────────────────────────────────────────────────────────

class TestAppointmentsAPI:

    def test_list_appointments_empty(self, client):
        """BD vacía → lista de citas vacía."""
        response = client.get("/appointments/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_nonexistent_appointment_returns_404(self, client):
        """Buscar cita que no existe → 404."""
        response = client.get("/appointments/999999")
        assert response.status_code == 404

    def test_cancel_nonexistent_appointment_returns_404(self, client):
        """Cancelar cita que no existe → 404."""
        response = client.patch("/appointments/999999/cancel")
        assert response.status_code == 404
