"""
Agente IA de la clínica — usa OpenAI function calling.
REGLA DE ORO: el LLM nunca toca la BD directamente.
Solo puede llamar las funciones de este módulo, que a su vez
llaman a core/availability.py.
"""

import os
import json
import asyncio
from datetime import datetime, date
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

# ── Definición de herramientas para OpenAI ────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "listar_doctores",
            "description": "Lista todos los doctores disponibles con sus especialidades e IDs"
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_tipos_cita",
            "description": "Lista los tipos de cita disponibles con duración e IDs"
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_disponibilidad",
            "description": "Consulta los huecos disponibles de un doctor para una fecha y tipo de cita concretos",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer", "description": "ID del doctor"},
                    "appointment_type_id": {"type": "integer", "description": "ID del tipo de cita"},
                    "fecha": {"type": "string", "description": "Fecha en formato YYYY-MM-DD"}
                },
                "required": ["doctor_id", "appointment_type_id", "fecha"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_paciente",
            "description": "Busca un paciente por número de teléfono",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Número de teléfono del paciente"}
                },
                "required": ["phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_paciente",
            "description": "Registra un nuevo paciente en el sistema",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string", "description": "Opcional"}
                },
                "required": ["name", "phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_cita",
            "description": "Crea una cita para el paciente. Siempre confirma los detalles antes de llamar esta función.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "integer"},
                    "doctor_id": {"type": "integer"},
                    "appointment_type_id": {"type": "integer"},
                    "start_datetime": {"type": "string", "description": "ISO format: 2025-01-15T09:00:00"},
                    "notes": {"type": "string", "description": "Notas opcionales"}
                },
                "required": ["patient_id", "doctor_id", "appointment_type_id", "start_datetime"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_citas_paciente",
            "description": "Ver las citas próximas de un paciente",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "integer"}
                },
                "required": ["patient_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancelar_cita",
            "description": "Cancela una cita existente",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer"}
                },
                "required": ["appointment_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_citas_del_dia",
            "description": "Lista todas las citas programadas para una fecha concreta. Úsala cuando alguien pregunte qué citas hay un día, cuántas citas hay, o quiera ver la agenda del día.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string", "description": "Fecha en formato YYYY-MM-DD"}
                },
                "required": ["fecha"]
            }
        }
    }
]

SYSTEM_PROMPT = """Eres el asistente virtual de la Clínica Dental Demo. Ayudas a los pacientes a gestionar sus citas de forma amable y eficiente por WhatsApp.

Puedes:
- Consultar disponibilidad de los doctores
- Crear, confirmar y cancelar citas
- Registrar nuevos pacientes
- Ver las citas próximas de un paciente
- Ver todas las citas agendadas para un día concreto (listar_citas_del_dia)

Reglas importantes:
- Antes de crear una cita, SIEMPRE confirma: doctor, tipo de cita, fecha y hora
- Si el paciente no está registrado, pide su nombre completo para registrarlo
- CRÍTICO: cuando llames a crear_cita, usa EXACTAMENTE el patient_id que devolvió registrar_paciente o buscar_paciente en esta misma conversación. Nunca uses un ID que no hayas obtenido en esta conversación.
- Cuando muestres huecos disponibles, muestra máximo 5-6 opciones para no abrumar al paciente
- Sé breve, amable y profesional — estás en un chat de WhatsApp, no en un email
- Usa siempre español de España
- Si el paciente dice "mañana", "el lunes", etc., calcula la fecha real (hoy es {today})
- Cuando confirmes una cita creada, incluye todos los detalles: doctor, tipo, fecha y hora
- Cuando alguien pregunte por las citas de un día, usa listar_citas_del_dia — NO consultar_disponibilidad
"""


class ClinicAgent:
    def __init__(self, db: Session, conversation_history: list = None):
        self.db = db
        self.conversation_history = conversation_history or []
        self._client = None

    def _get_client(self):
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY no configurada")
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    # ── Implementación de herramientas ────────────────────────────────────────

    def _listar_doctores(self) -> str:
        from app.models import Doctor
        doctors = self.db.query(Doctor).filter(Doctor.active == True).all()
        result = [{"id": d.id, "nombre": d.name, "especialidad": d.specialty} for d in doctors]
        return json.dumps(result, ensure_ascii=False)

    def _listar_tipos_cita(self) -> str:
        from app.models import AppointmentType
        types = self.db.query(AppointmentType).all()
        result = [{"id": t.id, "nombre": t.name, "duracion_minutos": t.duration_minutes} for t in types]
        return json.dumps(result, ensure_ascii=False)

    def _consultar_disponibilidad(self, doctor_id: int, appointment_type_id: int, fecha: str) -> str:
        from core.availability import check_availability
        try:
            target_date = datetime.strptime(fecha, "%Y-%m-%d").date()
            slots = check_availability(doctor_id, appointment_type_id, target_date, self.db)
            if not slots:
                return json.dumps({"disponible": False, "mensaje": "No hay huecos disponibles ese día"})
            return json.dumps({"disponible": True, "huecos": slots[:8]}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _buscar_paciente(self, phone: str) -> str:
        from app.models import Patient
        patient = self.db.query(Patient).filter(Patient.phone == phone).first()
        if not patient:
            return json.dumps({"encontrado": False})
        return json.dumps({
            "encontrado": True,
            "id": patient.id,
            "nombre": patient.name,
            "telefono": patient.phone,
            "email": patient.email
        }, ensure_ascii=False)

    def _registrar_paciente(self, name: str, phone: str, email: str = None) -> str:
        from app.models import Patient
        existing = self.db.query(Patient).filter(Patient.phone == phone).first()
        if existing:
            return json.dumps({"ok": True, "id": existing.id, "nombre": existing.name, "ya_existia": True})
        patient = Patient(name=name, phone=phone, email=email)
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        return json.dumps({"ok": True, "id": patient.id, "nombre": patient.name, "ya_existia": False})

    def _crear_cita(self, patient_id: int, doctor_id: int, appointment_type_id: int,
                    start_datetime: str, notes: str = None) -> str:
        from core.availability import create_appointment_safe
        try:
            dt = datetime.fromisoformat(start_datetime)
            appt = create_appointment_safe(patient_id, doctor_id, appointment_type_id, dt, notes, self.db)
            from app.models import Doctor, AppointmentType, Patient
            doctor = self.db.get(Doctor, doctor_id)
            atype = self.db.get(AppointmentType, appointment_type_id)
            patient = self.db.get(Patient, patient_id)
            # Sincronizar con Google Calendar (no bloquea si falla)
            try:
                from core.google_calendar import create_event_sync as gcal_create
                gcal_id = gcal_create(
                    patient_name=patient.name,
                    patient_phone=patient.phone,
                    doctor_name=doctor.name,
                    specialty=doctor.specialty,
                    appointment_type=atype.name,
                    start_dt=appt.start_datetime,
                    end_dt=appt.end_datetime,
                    notes=notes,
                )
                if gcal_id:
                    appt.gcal_event_id = gcal_id
                    self.db.commit()
            except Exception as gcal_err:
                import logging
                logging.getLogger("agent").warning(f"⚠️ gcal sync error (cita guardada igualmente): {gcal_err}")

            return json.dumps({
                "ok": True,
                "cita_id": appt.id,
                "paciente": patient.name,
                "doctor": doctor.name,
                "tipo": atype.name,
                "inicio": appt.start_datetime.strftime("%d/%m/%Y a las %H:%M"),
                "fin": appt.end_datetime.strftime("%H:%M")
            }, ensure_ascii=False)
        except ValueError as e:
            return json.dumps({"ok": False, "error": str(e)})

    def _ver_citas_paciente(self, patient_id: int) -> str:
        from app.models import Appointment
        now = datetime.utcnow()
        citas = self.db.query(Appointment).filter(
            Appointment.patient_id == patient_id,
            Appointment.start_datetime >= now,
            Appointment.status.in_(["scheduled", "confirmed"])
        ).order_by(Appointment.start_datetime).limit(5).all()
        if not citas:
            return json.dumps({"citas": [], "mensaje": "No tienes citas próximas"})
        result = [{
            "id": c.id,
            "doctor": c.doctor.name,
            "tipo": c.appointment_type.name,
            "fecha_hora": c.start_datetime.strftime("%d/%m/%Y a las %H:%M"),
            "estado": c.status
        } for c in citas]
        return json.dumps({"citas": result}, ensure_ascii=False)

    def _listar_citas_del_dia(self, fecha: str) -> str:
        from app.models import Appointment
        try:
            target_date = datetime.strptime(fecha, "%Y-%m-%d").date()
            day_start = datetime.combine(target_date, datetime.min.time())
            day_end = datetime.combine(target_date, datetime.max.time())
            citas = self.db.query(Appointment).filter(
                Appointment.start_datetime >= day_start,
                Appointment.start_datetime <= day_end,
                Appointment.status.in_(["scheduled", "confirmed"])
            ).order_by(Appointment.start_datetime).all()
            if not citas:
                return json.dumps({"citas": [], "mensaje": f"No hay citas programadas para el {fecha}"})
            result = [{
                "id": c.id,
                "paciente": c.patient.name,
                "doctor": c.doctor.name,
                "tipo": c.appointment_type.name,
                "hora_inicio": c.start_datetime.strftime("%H:%M"),
                "hora_fin": c.end_datetime.strftime("%H:%M"),
                "estado": c.status
            } for c in citas]
            return json.dumps({"fecha": fecha, "total": len(result), "citas": result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _cancelar_cita(self, appointment_id: int) -> str:
        from app.models import Appointment
        appt = self.db.get(Appointment, appointment_id)
        if not appt:
            return json.dumps({"ok": False, "error": "Cita no encontrada"})
        if appt.status in ("cancelled", "completed"):
            return json.dumps({"ok": False, "error": f"La cita ya está en estado '{appt.status}'"})
        appt.status = "cancelled"
        self.db.commit()
        return json.dumps({"ok": True, "mensaje": "Cita cancelada correctamente"})

    def _execute_tool(self, name: str, args: dict) -> str:
        """Ejecuta la herramienta solicitada por el modelo."""
        if name == "listar_doctores":
            return self._listar_doctores()
        elif name == "listar_tipos_cita":
            return self._listar_tipos_cita()
        elif name == "consultar_disponibilidad":
            return self._consultar_disponibilidad(**args)
        elif name == "buscar_paciente":
            return self._buscar_paciente(**args)
        elif name == "registrar_paciente":
            return self._registrar_paciente(**args)
        elif name == "crear_cita":
            return self._crear_cita(**args)
        elif name == "ver_citas_paciente":
            return self._ver_citas_paciente(**args)
        elif name == "cancelar_cita":
            return self._cancelar_cita(**args)
        elif name == "listar_citas_del_dia":
            return self._listar_citas_del_dia(**args)
        else:
            return json.dumps({"error": f"Herramienta desconocida: {name}"})

    # ── Loop principal ────────────────────────────────────────────────────────

    async def chat(self, user_message: str) -> str:
        """Procesa un mensaje del paciente y devuelve la respuesta del agente."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "⚠️ El asistente IA no está configurado todavía. Falta la clave OPENAI_API_KEY en el archivo .env"

        client = self._get_client()

        # Añadir mensaje del usuario al historial
        self.conversation_history.append({"role": "user", "content": user_message})

        system = SYSTEM_PROMPT.replace("{today}", date.today().strftime("%A %d de %B de %Y"))
        messages = [{"role": "system", "content": system}] + self.conversation_history

        # Loop de function calling
        MAX_ITERATIONS = 12
        for _ in range(MAX_ITERATIONS):
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3
            )

            msg = response.choices[0].message

            # Si no hay tool calls, tenemos la respuesta final
            if not msg.tool_calls:
                self.conversation_history.append({"role": "assistant", "content": msg.content})
                return msg.content

            # Ejecutar todas las tool calls
            messages.append(msg)
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                result = self._execute_tool(tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result
                })

        return "Lo siento, no he podido completar la solicitud. Por favor, inténtalo de nuevo."
