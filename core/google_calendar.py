"""
Integración con Google Calendar.
Crea, actualiza y elimina eventos cuando se gestionan citas en la clínica.
Usa OAuth2 con refresh token (configurado via get_google_token.py).
"""
import os
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

logger = logging.getLogger("gcal")
_executor = ThreadPoolExecutor(max_workers=2)

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("⚠️  google-api-python-client no instalado. Calendar desactivado.")


def _get_service():
    if not GOOGLE_AVAILABLE:
        return None
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not all([refresh_token, client_id, client_secret]):
        logger.warning("⚠️  Google Calendar no configurado (faltan variables en .env)")
        return None
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    # Refrescar el token antes de usar
    creds.refresh(Request())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _calendar_id() -> str:
    return os.getenv("GOOGLE_CALENDAR_ID", "primary")


# ── Funciones síncronas (se llaman desde el executor) ─────────────────────────

def _create_event_sync(patient_name, doctor_name, specialty, appointment_type,
                       start_dt, end_dt, notes=None, patient_phone=None):
    service = _get_service()
    if not service:
        return None
    description = "\n".join(filter(None, [
        f"👤 Paciente: {patient_name}",
        f"📞 Teléfono: {patient_phone}" if patient_phone else "",
        f"🩺 Doctor: {doctor_name} ({specialty})",
        f"📋 Tipo: {appointment_type}",
        f"📝 Notas: {notes}" if notes else "",
        "\n— Creado automáticamente por Clínica Demo"
    ]))
    event = {
        "summary": f"🦷 {patient_name} — {appointment_type}",
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Madrid"},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Europe/Madrid"},
        "colorId": "2",  # verde
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 60},
                {"method": "email", "minutes": 1440},
            ],
        },
    }
    try:
        result = service.events().insert(calendarId=_calendar_id(), body=event).execute()
        event_id = result.get("id")
        logger.warning(f"✅ Google Calendar: evento creado → {event_id} ({patient_name})")
        return event_id
    except Exception as e:
        logger.error(f"❌ Google Calendar create error: {e}")
        return None


def _cancel_event_sync(event_id):
    service = _get_service()
    if not service or not event_id:
        return False
    try:
        event = service.events().get(calendarId=_calendar_id(), eventId=event_id).execute()
        if not event["summary"].startswith("❌"):
            event["summary"] = "❌ CANCELADA — " + event["summary"]
        event["colorId"] = "11"  # rojo
        service.events().update(calendarId=_calendar_id(), eventId=event_id, body=event).execute()
        logger.warning(f"✅ Google Calendar: evento cancelado → {event_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Google Calendar cancel error: {e}")
        return False


def _confirm_event_sync(event_id):
    service = _get_service()
    if not service or not event_id:
        return False
    try:
        event = service.events().get(calendarId=_calendar_id(), eventId=event_id).execute()
        event["colorId"] = "9"  # azul
        event["summary"] = event["summary"].replace("🦷", "✅")
        service.events().update(calendarId=_calendar_id(), eventId=event_id, body=event).execute()
        logger.warning(f"✅ Google Calendar: evento confirmado → {event_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Google Calendar confirm error: {e}")
        return False


# ── API pública: versión async (no bloquea el servidor) ───────────────────────

async def create_event(patient_name, doctor_name, specialty, appointment_type,
                       start_dt, end_dt, notes=None, patient_phone=None) -> Optional[str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor, _create_event_sync,
        patient_name, doctor_name, specialty, appointment_type, start_dt, end_dt, notes, patient_phone
    )


async def cancel_event(event_id: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _cancel_event_sync, event_id)


async def confirm_event(event_id: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _confirm_event_sync, event_id)


# ── Versiones síncronas para el agente (que no es async) ──────────────────────

def create_event_sync(patient_name, doctor_name, specialty, appointment_type,
                      start_dt, end_dt, notes=None, patient_phone=None) -> Optional[str]:
    return _create_event_sync(patient_name, doctor_name, specialty, appointment_type,
                               start_dt, end_dt, notes, patient_phone)


def cancel_event_sync(event_id: str) -> bool:
    return _cancel_event_sync(event_id)


def confirm_event_sync(event_id: str) -> bool:
    return _confirm_event_sync(event_id)
