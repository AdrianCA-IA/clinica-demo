# 🏥 Checklist — Configuración para Cliente Nuevo

Guía paso a paso para instalar y configurar el sistema en una clínica nueva.
Tiempo estimado: 1-2 horas.

---

## Fase 1: Cuentas y credenciales

### OpenAI
- [ ] Crear cuenta en https://platform.openai.com (o usar existente)
- [ ] Crear API key en Settings → API Keys
- [ ] Configurar límite de gasto mensual en Settings → Billing
- [ ] Anotar la clave: `sk-...`

### Twilio
- [ ] Crear cuenta en https://twilio.com (o usar existente)
- [ ] Comprar un número de teléfono con capacidad de voz entrante
- [ ] Anotar:
  - Account SID: `AC...`
  - Auth Token: (en el dashboard principal)
  - Número de teléfono: `+34...`

### Google Cloud — Calendar
- [ ] Ir a https://console.cloud.google.com
- [ ] Crear proyecto nuevo (ej. "Clinica NombreCliente")
- [ ] Habilitar Google Calendar API: APIs & Services → Library → buscar "Google Calendar API" → Enable
- [ ] Crear credenciales OAuth2:
  - APIs & Services → Credentials → Create Credentials → OAuth client ID
  - Application type: **Desktop app**
  - Nombre: "Clinica Demo"
  - Descargar el JSON y guardarlo en `credentials/google_oauth.json`
- [ ] Configurar pantalla de consentimiento si se pide (modo Testing, añadir email del cliente como usuario de prueba)

---

## Fase 2: Instalación del sistema

- [ ] Clonar o copiar el proyecto al servidor/ordenador del cliente
- [ ] Crear entorno virtual: `python -m venv venv`
- [ ] Activar entorno virtual
- [ ] Instalar dependencias: `pip install -r requirements.txt`

---

## Fase 3: Obtener token de Google Calendar

```bash
python get_google_token.py
```

- [ ] Seguir el enlace que aparece en pantalla
- [ ] Iniciar sesión con la cuenta Google del cliente (la que tiene el calendario)
- [ ] Autorizar el acceso
- [ ] Copiar los tres valores que imprime el script:
  - `GOOGLE_REFRESH_TOKEN=...`
  - `GOOGLE_CLIENT_ID=...`
  - `GOOGLE_CLIENT_SECRET=...`

---

## Fase 4: Configurar variables de entorno

- [ ] Copiar `.env.example` → `.env`
- [ ] Rellenar **todas** las variables:

```env
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+34...
GOOGLE_REFRESH_TOKEN=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_CALENDAR_ID=primary
DATABASE_URL=sqlite:///./clinica.db
```

---

## Fase 5: Personalizar datos de la clínica

Editar `seed_data.py` con los datos reales del cliente:

- [ ] Nombre de la clínica (en el prompt del agente en `agent/agent.py`)
- [ ] **Doctores**: nombre, especialidad
- [ ] **Tipos de cita**: nombre, duración en minutos, precio (opcional)
- [ ] **Horarios**: días laborables, hora inicio, hora fin, tiempo por hueco

---

## Fase 6: Preparar la base de datos

```bash
python seed_data.py        # crea tablas y carga datos
python migrate_add_gcal.py # añade columna de sincronización Calendar
```

- [ ] Verificar que no hay errores
- [ ] Comprobar en `/docs` que los endpoints responden

---

## Fase 7: Arrancar el servidor y configurar Twilio

- [ ] Arrancar servidor: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- [ ] Iniciar túnel: `cloudflared tunnel --url http://localhost:8000`
- [ ] Copiar URL pública del túnel (ej. `https://xxxx.trycloudflare.com`)
- [ ] En Twilio Console → Phone Numbers → Tu número → Voice:
  - Webhook URL: `https://xxxx.trycloudflare.com/twilio/voice`
  - HTTP Method: POST
  - Guardar

---

## Fase 8: Pruebas de verificación

### Chat
- [ ] Abrir `http://localhost:8000/chat`
- [ ] Enviar "Hola" — el agente debe responder
- [ ] Reservar una cita de prueba completa (nombre, teléfono, doctor, fecha, hora)
- [ ] Verificar que la cita aparece en Google Calendar del cliente
- [ ] Cancelar la cita — verificar que en Calendar aparece como cancelada (rojo)

### Llamada de voz
- [ ] Llamar al número de Twilio desde un teléfono
- [ ] Verificar que contesta la IA
- [ ] Completar una reserva por voz
- [ ] Verificar que la cita aparece en la BD y en Calendar

### API
- [ ] Abrir `http://localhost:8000/docs`
- [ ] Probar `GET /patients/` — lista pacientes de prueba
- [ ] Probar `GET /appointments/` — lista citas creadas

---

## Fase 9: Despliegue en producción (opcional)

Si el cliente quiere el servidor siempre activo en la nube:

- [ ] Seguir la guía completa en [DEPLOY.md](DEPLOY.md)
- [ ] Actualizar el webhook de Twilio con la URL definitiva de producción
- [ ] Borrar los pacientes y citas de prueba de la BD

---

## ⚠️ Notas importantes

- **No subir `.env` ni la carpeta `credentials/` a Git** — contienen secretos
- **Rotar el Auth Token de Twilio** si fue compartido por email o similar
- **El refresh token de Google no caduca** (salvo que el usuario revoque el acceso), pero si caduca se debe volver a ejecutar `get_google_token.py`
- **En producción usar PostgreSQL** en vez de SQLite para mejor rendimiento y concurrencia

---

## Tiempos estimados por fase

| Fase | Tiempo estimado |
|------|----------------|
| Cuentas y credenciales | 30-45 min |
| Instalación | 10 min |
| Token Google Calendar | 5 min |
| Configurar .env | 5 min |
| Personalizar datos clínica | 20-30 min |
| Preparar BD | 5 min |
| Twilio + pruebas | 15 min |
| **Total** | **~1h 30min** |
