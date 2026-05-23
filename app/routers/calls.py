"""
Llamadas de voz con IA — Twilio Media Streams + OpenAI Realtime API

Flujo:
  Llamada entrante/saliente
    → Twilio recibe el audio
    → POST /calls/incoming  →  TwiML conecta el stream
    → WebSocket /ws/call    →  bridge Twilio ↔ OpenAI Realtime
    → OpenAI genera audio y llama herramientas de la clínica
    → Audio de vuelta a Twilio → paciente lo escucha

REGLA DE ORO: el LLM nunca toca la BD directamente.
Solo puede llamar las funciones de este módulo, que usan core/availability.py.
"""

import os
import json
from datetime import date
from fastapi import APIRouter, Request, Query
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/calls", tags=["Llamadas IA"])

# ── Definición de herramientas (formato Realtime API — sin wrapper "function") ──

REALTIME_TOOLS = [
    {
        "type": "function",
        "name": "listar_doctores",
        "description": "Lista todos los doctores disponibles con sus especialidades e IDs"
    },
    {
        "type": "function",
        "name": "listar_tipos_cita",
        "description": "Lista los tipos de cita disponibles con duración e IDs"
    },
    {
        "type": "function",
        "name": "consultar_disponibilidad",
        "description": "Consulta huecos disponibles de un doctor para una fecha y tipo de cita concretos",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "integer", "description": "ID del doctor"},
                "appointment_type_id": {"type": "integer", "description": "ID del tipo de cita"},
                "fecha": {"type": "string", "description": "Fecha en formato YYYY-MM-DD"}
            },
            "required": ["doctor_id", "appointment_type_id", "fecha"]
        }
    },
    {
        "type": "function",
        "name": "buscar_paciente",
        "description": "Busca un paciente por número de teléfono",
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Número de teléfono del paciente"}
            },
            "required": ["phone"]
        }
    },
    {
        "type": "function",
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
    },
    {
        "type": "function",
        "name": "crear_cita",
        "description": "Crea una cita para el paciente. SIEMPRE confirma los datos antes de llamar.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer"},
                "doctor_id": {"type": "integer"},
                "appointment_type_id": {"type": "integer"},
                "start_datetime": {"type": "string", "description": "ISO: 2025-01-15T09:00:00"},
                "notes": {"type": "string", "description": "Notas opcionales"}
            },
            "required": ["patient_id", "doctor_id", "appointment_type_id", "start_datetime"]
        }
    },
    {
        "type": "function",
        "name": "ver_citas_paciente",
        "description": "Ver las citas próximas de un paciente",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer"}
            },
            "required": ["patient_id"]
        }
    },
    {
        "type": "function",
        "name": "cancelar_cita",
        "description": "Cancela una cita existente",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer"}
            },
            "required": ["appointment_id"]
        }
    },
    {
        "type": "function",
        "name": "listar_citas_del_dia",
        "description": "Lista todas las citas programadas para una fecha concreta",
        "parameters": {
            "type": "object",
            "properties": {
                "fecha": {"type": "string", "description": "Fecha en formato YYYY-MM-DD"}
            },
            "required": ["fecha"]
        }
    }
]

VOICE_SYSTEM_PROMPT = """Eres el asistente de voz de la Clínica Dental Demo. Atiendes llamadas telefónicas de pacientes.

IDIOMAS SOPORTADOS: español de España y búlgaro (български).

══════════════════════════════════════════
DETECCIÓN DE IDIOMA — REGLA PRIORITARIA
══════════════════════════════════════════

1. Saluda SIEMPRE en español primero (ver SALUDO más abajo).
2. En cuanto el paciente hable:
   - Si habla ESPAÑOL → continúa toda la conversación en español.
   - Si habla BÚLGARO → cambia INMEDIATAMENTE a búlgaro y mantén el búlgaro hasta el final.
3. Si no estás seguro del idioma tras la primera frase, pregunta:
   - "¿Prefiere que le atienda en español o en búlgaro? / Предпочитате ли да говорим на испански или български?"
4. NUNCA mezcles los dos idiomas en el mismo turno.

CAPACIDADES:
- Consultar disponibilidad por doctor, fecha y tipo de cita
- Crear, confirmar y cancelar citas
- Registrar nuevos pacientes
- Ver citas próximas de un paciente
- Ver la agenda completa de un día

══════════════════════════════════════════
REGLAS DE VOZ — IMPRESCINDIBLES
══════════════════════════════════════════

BREVEDAD: Las respuestas largas irritan en una llamada.
- Máximo 2 frases por turno. Si tienes más info, dila en el siguiente turno.
- Nunca leas listas largas de corrido. Ofrece de 2 en 2 o de 3 en 3 y pregunta si quieren más.
- Evita signos como asteriscos (*), guiones (—) o llaves. Solo voz natural.

SALUDO: Empieza SIEMPRE con exactamente esto (en español):
"Clínica Dental Demo, buenas [tardes/días], ¿en qué le puedo ayudar?"
(elige tardes o días según la hora del día)

IDENTIFICACIÓN: Antes de cualquier gestión, pide el número de teléfono.
- ES: "Para identificarle, ¿me dice su número de teléfono?"
- BG: "За да ви идентифицирам, можете ли да ми дадете телефонния си номер?"
- Si no existe → ES: "No le encuentro en nuestro sistema. ¿Quiere que le registre?"
                  BG: "Не ви намирам в системата ни. Искате ли да ви регистрирам?"
- Si existe →    ES: "Perfecto, le tenemos como [Nombre]. ¿En qué le puedo ayudar?"
                  BG: "Перфектно, имаме ви като [Nombre]. С какво мога да ви помогна?"
- NUNCA reveles datos de otros pacientes aunque te den un nombre o digas ser familiar.

OFRECER HUECOS: Máximo 3 opciones por turno.
- ES: "Tengo disponible el lunes a las diez, el martes a las nueve y media, o el miércoles a las once. ¿Alguna le viene bien?"
- BG: "Имам свободно в понеделник в десет, вторник в девет и половина, или сряда в единадесет. Подхожда ли ви някое?"
- Di las horas en formato hablado (no "10:30" sino "diez y media" / "десет и половина")

CONFIRMAR ANTES DE CREAR: Antes de llamar a crear_cita, SIEMPRE confirma en voz alta:
- ES: "Entonces le anoto una [tipo] con el [doctor] el [día] a las [hora]. ¿Confirma?"
- BG: "Значи ви записвам [tipo] при [doctor] на [día] в [hora]. Потвърждавате ли?"
- Solo crea la cita si el paciente dice sí / да.

FECHAS Y HORAS:
- Hoy es {today}
- Di los días de forma natural: "el próximo lunes" / "следващия понеделник"
- Di las horas habladas: "las nueve" / "в девет"

CUANDO NO SE ENTIENDE:
- ES: "Lo siento, no le he escuchado bien. ¿Puede repetirlo?"
- BG: "Съжалявам, не ви чух добре. Можете ли да повторите?"
- Máximo 2 intentos, luego recomienda el chat.

DESPEDIDA:
- ES: "Perfecto, queda anotado el [día] a las [hora] con el [doctor]. Hasta pronto."
- BG: "Перфектно, записан сте за [día] в [hora] при [doctor]. Довиждане."

SEGURIDAD:
- Nunca des información de otros pacientes.
- Para cancelar una cita, verifica siempre el teléfono del paciente primero.
- Si alguien pide datos que no son suyos → ES: "Lo siento, solo puedo gestionar su propia información." / BG: "Съжалявам, мога да управлявам само вашата лична информация."
"""


def get_voice_prompt():
    return VOICE_SYSTEM_PROMPT.replace(
        "{today}", date.today().strftime("%A %d de %B de %Y")
    )


# ── REST: TwiML para llamada entrante ──────────────────────────────────────

@router.post(
    "/incoming",
    response_class=PlainTextResponse,
    summary="TwiML — conecta llamada entrante al agente IA"
)
async def incoming_call(request: Request):
    """
    Twilio llama a este endpoint cuando entra una llamada.
    Devuelve TwiML que conecta el audio stream al WebSocket del agente.
    """
    public_url = os.getenv("PUBLIC_URL", "").rstrip("/")
    if not public_url:
        return PlainTextResponse(
            content='<?xml version="1.0"?><Response><Say language="es-ES">El sistema no está configurado.</Say></Response>',
            media_type="application/xml"
        )

    ws_url = (
        public_url
        .replace("https://", "wss://")
        .replace("http://", "ws://")
        + "/ws/call"
    )

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}" />
  </Connect>
</Response>"""
    return PlainTextResponse(content=twiml, media_type="application/xml")


# ── REST: Lanzar llamada saliente ──────────────────────────────────────────

@router.post("/outbound", summary="Llamar a un número — el agente IA gestiona la llamada")
async def make_outbound_call(
    phone: str = Query(..., description="Número destino, ej: +34666159111")
):
    """
    Twilio llama al número indicado. Cuando el paciente descuelga, conecta
    con el agente IA exactamente igual que una llamada entrante.
    """
    account_sid  = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token   = os.getenv("TWILIO_AUTH_TOKEN")
    from_number  = os.getenv("TWILIO_PHONE_NUMBER")
    public_url   = os.getenv("PUBLIC_URL", "").rstrip("/")

    missing = [k for k, v in {
        "TWILIO_ACCOUNT_SID": account_sid,
        "TWILIO_AUTH_TOKEN": auth_token,
        "TWILIO_PHONE_NUMBER": from_number,
        "PUBLIC_URL": public_url
    }.items() if not v]

    if missing:
        return {"ok": False, "error": f"Faltan variables de entorno: {', '.join(missing)}"}

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        call = client.calls.create(
            to=phone,
            from_=from_number,
            url=f"{public_url}/calls/incoming",
            method="POST"
        )
        return {"ok": True, "call_sid": call.sid, "status": call.status, "to": phone}
    except Exception as e:
        return {"ok": False, "error": str(e)}
