# 🦷 Clínica Demo — Asistente IA de Gestión de Citas

Sistema completo de gestión de citas para clínicas dentales, con asistente de inteligencia artificial por chat y llamadas de voz, sincronización con Google Calendar y API REST.

---

## ✨ Funcionalidades

- **Chat IA** — Pacientes reservan, modifican y cancelan citas por chat (WhatsApp-style)
- **Llamadas de voz** — Reserva de citas por teléfono con IA en tiempo real (OpenAI Realtime API + Twilio)
- **Google Calendar** — Sincronización automática de citas al crear, cancelar o confirmar
- **API REST** — Endpoints completos para integración con otros sistemas (`/docs`)
- **Gestión de pacientes** — Registro automático de nuevos pacientes durante la conversación

---

## 🛠️ Stack tecnológico

| Componente | Tecnología |
|---|---|
| Backend | FastAPI + Uvicorn |
| Base de datos | SQLite (producción: PostgreSQL) |
| ORM | SQLAlchemy |
| Agente IA (chat) | OpenAI gpt-4o-mini con function calling |
| Agente IA (voz) | OpenAI Realtime API (`gpt-realtime-1.5`) |
| Telefonía | Twilio (Voice + WebSocket) |
| Calendario | Google Calendar API v3 (OAuth2) |
| Túnel local | Cloudflare Tunnel o ngrok |

---

## 📁 Estructura del proyecto

```
clinica-demo/
├── app/
│   ├── main.py              # FastAPI app, WebSocket de voz y chat
│   ├── models.py            # Modelos SQLAlchemy
│   ├── schemas.py           # Schemas Pydantic
│   ├── database.py          # Conexión a BD
│   └── routers/
│       ├── appointments.py  # CRUD citas + sync Calendar
│       ├── patients.py      # CRUD pacientes
│       ├── doctors.py       # CRUD doctores
│       └── appointment_types.py
├── agent/
│   └── agent.py             # Agente IA (chat) con function calling
├── core/
│   ├── availability.py      # Lógica de disponibilidad y creación segura de citas
│   └── google_calendar.py   # Integración Google Calendar
├── static/
│   └── chat.html            # Interfaz de chat
├── credentials/             # OAuth2 de Google (NO subir a Git)
├── docs/
│   ├── DEPLOY.md            # Guía de despliegue en producción
│   └── NUEVO_CLIENTE.md     # Checklist para configurar cliente nuevo
├── .env                     # Variables de entorno (NO subir a Git)
├── .env.example             # Plantilla de variables
├── .gitignore
├── requirements.txt
├── seed_data.py             # Datos iniciales (doctores, tipos de cita, horarios)
├── migrate_add_gcal.py      # Migración BD: añade columna gcal_event_id
├── get_google_token.py      # Obtener refresh token de Google Calendar
└── reiniciar_servidor.bat   # Script de reinicio rápido (Windows)
```

---

## 🚀 Instalación

### 1. Requisitos previos

- Python 3.10 o superior
- Cuenta OpenAI con acceso a la API
- Cuenta Twilio con número de teléfono
- Proyecto en Google Cloud con Calendar API habilitada
- Cloudflare Tunnel o ngrok (para exponer el servidor localmente)

### 2. Clonar e instalar dependencias

```bash
git clone https://github.com/tu-usuario/clinica-demo.git
cd clinica-demo
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales (ver `.env.example` para descripción de cada variable).

### 4. Preparar la base de datos

```bash
# Crear tablas y cargar datos iniciales
python seed_data.py

# Añadir columna de Google Calendar (si la BD ya existía antes)
python migrate_add_gcal.py
```

### 5. Obtener token de Google Calendar

```bash
python get_google_token.py
```

Sigue las instrucciones en pantalla. Al finalizar, copia los valores en tu `.env`.

### 6. Arrancar el servidor

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

En Windows también puedes hacer doble clic en `reiniciar_servidor.bat`.

---

## 🌐 URLs disponibles

| URL | Descripción |
|---|---|
| `http://localhost:8000/chat` | Interfaz de chat con el asistente |
| `http://localhost:8000/docs` | Documentación Swagger de la API |
| `http://localhost:8000/redoc` | Documentación ReDoc de la API |

---

## 📞 Configuración de Twilio (llamadas de voz)

1. Inicia el túnel: `cloudflared tunnel --url http://localhost:8000`
2. Copia la URL pública (ej. `https://xxxx.trycloudflare.com`)
3. En Twilio Console → Tu número → Voice → Webhook: `https://xxxx.trycloudflare.com/twilio/voice`
4. Método: HTTP POST

---

## 🔑 Variables de entorno

Ver `.env.example` para la lista completa. Variables obligatorias:

- `OPENAI_API_KEY` — Clave de API de OpenAI
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` — Credenciales Twilio
- `GOOGLE_REFRESH_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — OAuth2 Google
- `GOOGLE_CALENDAR_ID` — ID del calendario (normalmente `primary`)

---

## 📚 Documentación adicional

- [Guía de despliegue en producción](docs/DEPLOY.md)
- [Checklist para nuevo cliente](docs/NUEVO_CLIENTE.md)

---

## 🗺️ Roadmap

- [ ] Migración SQLite → PostgreSQL
- [ ] Notificaciones SMS al confirmar cita
- [ ] Panel de administración web
- [ ] Docker Compose para despliegue simplificado
- [ ] Soporte multiclínica / multitenant
