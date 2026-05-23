"""
Test de conectividad completo — clinica-demo
Comprueba: OpenAI Realtime, Google Calendar, Base de datos, Twilio
Ejecutar: python test_todo.py
"""
import asyncio
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ─── colores ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✅ {msg}{RESET}")
def fail(msg): print(f"  {RED}❌ {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}⚠️  {msg}{RESET}")
def head(msg): print(f"\n{'═'*50}\n  {msg}\n{'─'*50}")


# ══════════════════════════════════════════════════════
# 1. OPENAI REALTIME
# ══════════════════════════════════════════════════════

async def test_openai():
    head("1 · OpenAI Realtime API")
    try:
        import websockets
    except ImportError:
        fail("Falta websockets: pip install websockets")
        return False

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        fail("OPENAI_API_KEY no encontrada en .env")
        return False

    model = "gpt-realtime-1.5"
    url   = f"wss://api.openai.com/v1/realtime?model={model}"

    try:
        async with websockets.connect(
            url,
            additional_headers={"Authorization": f"Bearer {api_key}"},
            open_timeout=10
        ) as ws:
            msg  = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            if data.get("type") == "session.created":
                sid = data.get("session", {}).get("id", "N/A")
                ok(f"Conexión OK — session_id: {sid}")
                ok(f"Modelo: {data.get('session', {}).get('model', model)}")
                return True
            else:
                warn(f"Respuesta inesperada: {data.get('type')}")
                return False
    except Exception as e:
        status = getattr(e, "status_code", None)
        if status == 401:
            fail("API key inválida o sin permisos para Realtime")
        elif status == 404:
            fail(f"Modelo '{model}' no encontrado — prueba gpt-4o-realtime-preview")
        elif status == 429:
            fail("Rate limit o créditos insuficientes")
        else:
            fail(f"{type(e).__name__}: {e}")
        return False


# ══════════════════════════════════════════════════════
# 2. GOOGLE CALENDAR
# ══════════════════════════════════════════════════════

def test_google():
    head("2 · Google Calendar")

    client_id     = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    calendar_id   = os.getenv("GOOGLE_CALENDAR_ID", "primary")

    # Comprobar variables
    missing = []
    if not client_id:     missing.append("GOOGLE_CLIENT_ID")
    if not client_secret: missing.append("GOOGLE_CLIENT_SECRET")
    if not refresh_token: missing.append("GOOGLE_REFRESH_TOKEN")

    if missing:
        fail(f"Variables no configuradas: {', '.join(missing)}")
        if "GOOGLE_REFRESH_TOKEN" in missing:
            warn("Para obtener el token ejecuta: python get_google_token.py")
        return False

    ok("Variables de entorno presentes")

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        fail("Falta google-api-python-client: pip install google-api-python-client google-auth")
        return False

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        # Leer el calendario
        cal = service.calendars().get(calendarId=calendar_id).execute()
        ok(f"Conexión OK — calendario: {cal.get('summary', calendar_id)}")

        # Listar próximos 3 eventos
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=3,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        events = events_result.get("items", [])
        ok(f"Próximos eventos en el calendario: {len(events)}")
        for ev in events:
            start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", "?"))
            ok(f"  → {ev.get('summary', '(sin título)')} — {start}")
        return True

    except Exception as e:
        err = str(e)
        if "invalid_grant" in err or "Token has been expired" in err:
            fail("Refresh token inválido o expirado")
            warn("Ejecuta: python get_google_token.py  para obtener uno nuevo")
        elif "403" in err or "insufficientPermissions" in err:
            fail("Sin permisos para este calendario")
        else:
            fail(f"{type(e).__name__}: {e}")
        return False


# ══════════════════════════════════════════════════════
# 3. BASE DE DATOS
# ══════════════════════════════════════════════════════

def test_database():
    head("3 · Base de datos (SQLite)")

    db_url = os.getenv("DATABASE_URL", "sqlite:///./clinica.db")
    ok(f"DATABASE_URL: {db_url}")

    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(db_url, connect_args={"check_same_thread": False})

        with engine.connect() as conn:
            # Listar tablas
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [r[0] for r in result]
            if tables:
                ok(f"Tablas encontradas: {', '.join(tables)}")
            else:
                warn("La BD está vacía (sin tablas). ¿Has ejecutado el servidor alguna vez?")
                return False

            # Contar registros en tablas clave
            for table in ["patients", "doctors", "appointments", "appointment_types"]:
                if table in tables:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    ok(f"  {table}: {count} registros")
                else:
                    warn(f"  Tabla '{table}' no existe")

        return True

    except Exception as e:
        fail(f"{type(e).__name__}: {e}")
        return False


# ══════════════════════════════════════════════════════
# 4. TWILIO
# ══════════════════════════════════════════════════════

def test_twilio():
    head("4 · Twilio")

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
    phone       = os.getenv("TWILIO_PHONE_NUMBER")
    public_url  = os.getenv("PUBLIC_URL", "")

    missing = []
    if not account_sid: missing.append("TWILIO_ACCOUNT_SID")
    if not auth_token:  missing.append("TWILIO_AUTH_TOKEN")
    if not phone:       missing.append("TWILIO_PHONE_NUMBER")

    if missing:
        fail(f"Variables no configuradas: {', '.join(missing)}")
        return False

    ok(f"Número Twilio: {phone}")
    ok(f"PUBLIC_URL:    {public_url or '(vacía)'}")

    if not public_url:
        warn("PUBLIC_URL vacía — el webhook de Twilio no funcionará")
    elif len(public_url) < 20:
        warn(f"PUBLIC_URL parece truncada: '{public_url}'")
    else:
        ok(f"PUBLIC_URL completa ({len(public_url)} chars)")

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)

        # Verificar la cuenta
        account = client.api.accounts(account_sid).fetch()
        ok(f"Cuenta Twilio OK — {account.friendly_name} ({account.status})")

        # Verificar que el número existe en la cuenta
        numbers = client.incoming_phone_numbers.list(phone_number=phone)
        if numbers:
            ok(f"Número verificado en la cuenta: {phone}")
        else:
            warn(f"El número {phone} no se encontró en esta cuenta")

        return True

    except Exception as e:
        err = str(e)
        if "authenticate" in err.lower() or "20003" in err:
            fail("Credenciales Twilio inválidas (Account SID / Auth Token)")
        elif "20404" in err:
            fail("Account SID no encontrado")
        else:
            fail(f"{type(e).__name__}: {e}")
        return False


# ══════════════════════════════════════════════════════
# RESUMEN
# ══════════════════════════════════════════════════════

async def main():
    print("\n" + "═"*50)
    print("  TEST COMPLETO — Clinica Demo")
    print("═"*50)

    results = {}

    results["OpenAI Realtime"] = await test_openai()
    results["Google Calendar"] = test_google()
    results["Base de datos"]   = test_database()
    results["Twilio"]          = test_twilio()

    head("RESUMEN")
    all_ok = True
    for name, passed in results.items():
        if passed:
            ok(name)
        else:
            fail(name)
            all_ok = False

    print()
    if all_ok:
        print(f"  {GREEN}Todo OK — el sistema está listo.{RESET}")
    else:
        print(f"  {YELLOW}Hay servicios pendientes de configurar (ver detalles arriba).{RESET}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
