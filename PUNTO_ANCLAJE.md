# 📍 Punto de Anclaje — Clinica Demo v2.2
**Fecha:** 21 mayo 2026  
**Estado:** ✅ Sistema funcionando con llamadas de voz + sincronización Google Calendar

---

## ✅ Qué funciona ahora mismo

| Componente | Estado | Notas |
|---|---|---|
| Chat IA (WebSocket) | ✅ Funciona | `/chat` — crea citas, busca pacientes, cancela |
| Llamadas de voz (Twilio + OpenAI) | ✅ Funciona | Saludo, VAD con 2s de paciencia, herramientas conectadas |
| Base de datos (SQLite) | ✅ Funciona | Citas + pacientes |
| Twilio API | ✅ Funciona | Cuenta activa, número +17627700780 |
| OpenAI Realtime API | ✅ Funciona | Modelo gpt-realtime-1.5 |
| Google Calendar | ✅ Funciona | Eventos incluyen teléfono del paciente |
| Soporte bilingüe | ✅ Nuevo | Español + Búlgaro — detección automática |
| Teléfono en calendario | ✅ Nuevo | Se muestra en descripción del evento |
| VAD timeout | ✅ Mejorado | 2000ms (antes cortaba al dar el teléfono) |
| Cambio de voz durante llamada | ⚠️ Bug conocido | Voz cambia de género a mitad de llamada |

---

## 🔧 Configuración actual que funciona

### session.update (formato correcto para Twilio + OpenAI Realtime)
```python
{
    "type": "session.update",
    "session": {
        "type": "realtime",
        "output_modalities": ["audio"],
        "audio": {
            "input": {
                "format": {"type": "audio/pcmu"},
                "turn_detection": {
                    "type": "server_vad",
                    "silence_duration_ms": 2000,   # ← 2 segundos de paciencia
                    "threshold": 0.5
                }
            },
            "output": {
                "format": {"type": "audio/pcmu"},
                "voice": "alloy"
            }
        },
        "instructions": get_voice_prompt(),
        "tools": REALTIME_TOOLS,
        "tool_choice": "auto"
    }
}
```

### Evento de audio correcto (OpenAI → Twilio)
```python
if mtype == "response.output_audio.delta":   # ← este, NO response.audio.delta
```

---

## 🌐 URLs y variables de entorno

> ⚠️ **IMPORTANTE:** La URL de Cloudflare cambia cada vez que se reinicia el túnel.  
> Cada vez que cambie hay que actualizarla en DOS sitios:
> 1. `.env` → `PUBLIC_URL=https://nueva-url.trycloudflare.com`
> 2. Consola Twilio → número → Voice webhook → `https://nueva-url.trycloudflare.com/calls/incoming`

### Variables en .env (referencia)
```
OPENAI_API_KEY=sk-proj-...            ✅
TWILIO_ACCOUNT_SID=AC28f...          ✅
TWILIO_AUTH_TOKEN=97ef...            ✅
TWILIO_PHONE_NUMBER=+17627700780     ✅
PUBLIC_URL=https://[URL-CLOUDFLARE].trycloudflare.com   ← actualizar en cada reinicio
GOOGLE_CLIENT_ID=606154889064-...    ✅
GOOGLE_CLIENT_SECRET=GOCSPX-...     ✅
GOOGLE_REFRESH_TOKEN=1//03NB-...    ✅ (103 chars — correcto)
GOOGLE_CALENDAR_ID=primary          ✅
DATABASE_URL=sqlite:///./clinica.db  ✅
```

---

## 🚀 Cómo arrancar el sistema

1. Iniciar Cloudflare:
   ```
   cloudflared tunnel --url http://localhost:8000
   ```
2. Copiar la nueva URL que muestra Cloudflare
3. Actualizar `.env` → `PUBLIC_URL=https://nueva-url.trycloudflare.com`
4. Actualizar consola Twilio → Voice webhook → `https://nueva-url.trycloudflare.com/calls/incoming`
5. Ejecutar `reiniciar_servidor.bat` (doble clic — NO uvicorn manual, NO --reload)
6. Verificar: `python test_todo.py`

---

## 🔄 Sincronizar citas antiguas con Google Calendar

Si hay citas en la BD sin `gcal_event_id`, usar:

```bash
# Ver qué se sincronizaría (sin crear nada)
python sync_gcal_old.py --dry-run

# Sincronizar de verdad
python sync_gcal_old.py

# Borrar TODO (BD + Google Calendar) para empezar de cero
python sync_gcal_old.py --delete
```

---

## 🌍 Idiomas soportados en llamadas de voz

- **Español** (por defecto — saludo inicial)
- **Búlgaro** — si el paciente habla en búlgaro, el asistente cambia automáticamente al búlgaro

Configurado en `VOICE_SYSTEM_PROMPT` en `app/routers/calls.py`.

---

## 🐛 Bugs pendientes de resolver

### 1. Voz cambia de género durante la llamada (prioridad baja)
- **Síntoma:** La IA empieza con una voz y cambia a mitad de conversación
- **Posible causa:** OpenAI genera el saludo inicial con una voz y luego cambia (comportamiento del modelo)
- **Fix a investigar:** Forzar voz consistente en `session.update`, o actualizar modelo a gpt-4o-realtime-preview

---

## 📁 Estructura del proyecto

```
clinica-demo/
├── app/
│   ├── main.py           ← FastAPI + WebSocket bridge Twilio↔OpenAI (ws/call) + chat (ws/chat)
│   ├── routers/
│   │   ├── appointments.py   ← CRUD citas + Google Calendar sync (con teléfono)
│   │   ├── calls.py          ← TwiML + REALTIME_TOOLS + VOICE_SYSTEM_PROMPT (bilingüe ES+BG)
│   │   ├── patients.py
│   │   ├── doctors.py
│   │   └── availability.py
│   ├── models.py
│   ├── schemas.py
│   └── database.py
├── agent/
│   └── agent.py          ← Agente chat IA (OpenAI function calling)
├── core/
│   ├── availability.py   ← Lógica de huecos y creación de citas
│   └── google_calendar.py   ← Incluye patient_phone en descripción del evento
├── static/
│   └── index.html        ← UI chat estilo WhatsApp
├── tests/
│   ├── test_availability.py
│   └── test_patients_api.py
├── docs/
│   ├── DEPLOY.md
│   └── NUEVO_CLIENTE.md
├── .env                  ← ⚠️ actualizar PUBLIC_URL en cada reinicio de Cloudflare
├── reiniciar_servidor.bat ← usar SIEMPRE este para arrancar (sin --reload)
├── sync_gcal_old.py      ← sincronizar citas antiguas con Google Calendar
├── test_todo.py          ← diagnóstico completo de conectividad
└── README.md
```

---

## 🔮 Próximos pasos (roadmap)

1. **Arreglar cambio de voz** — investigar session.update voice lock
2. **URL fija de Cloudflare** — usar cuenta Cloudflare con tunnel named para URL permanente
3. **Notificaciones SMS** — Twilio SMS al crear/cancelar cita
4. **PostgreSQL** — migrar de SQLite para producción
5. **Repositorio GitHub** — subir código con CI/CD
