from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import json
import asyncio

from app.database import engine, Base, get_db
from app.routers import patients, doctors, appointments, availability, calls

# Crear todas las tablas al arrancar
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Clínica Demo — Sistema de Citas con IA",
    description="""
## Sistema de gestión de citas para clínica dental

**Parte 1+2 — Backend + Agente IA (WhatsApp chat)**

### Chat con IA
Abre **[/chat](/chat)** para hablar con el asistente virtual.

### Flujo principal (API REST)
1. Busca un paciente por teléfono (`GET /patients/phone/{phone}`)
2. Crea el paciente si no existe (`POST /patients`)
3. Consulta disponibilidad de un doctor (`GET /availability/doctor/{id}`)
4. Crea la cita en un hueco disponible (`POST /appointments`)
5. Confirma o cancela la cita

### Regla de oro
El LLM solo llama funciones de `core/availability.py`.
**Nunca** escribe directamente en la base de datos.
    """,
    version="2.0.0"
)

# CORS abierto para desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers REST
app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(availability.router)
app.include_router(calls.router)

# Servir archivos estáticos
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", tags=["Sistema"])
def root():
    return {
        "sistema": "Clínica Demo — Sistema de Citas con IA",
        "version": "2.0.0",
        "chat_ui": "/chat",
        "docs": "/docs",
    }


@app.get("/chat", tags=["Chat IA"], include_in_schema=False)
def chat_ui():
    """Sirve la interfaz de chat estilo WhatsApp."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    return FileResponse(html_path)


@app.get("/calendar", tags=["Calendario"], include_in_schema=False)
def calendar_ui():
    """Sirve el calendario de citas."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "static", "calendar.html")
    return FileResponse(html_path)


@app.websocket("/ws/call")
async def call_media_stream(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    Bridge WebSocket entre Twilio Media Streams y OpenAI Realtime API.
    Audio formato g711_ulaw (mulaw 8kHz).
    """
    import websockets as ws_lib
    from app.routers.calls import REALTIME_TOOLS, get_voice_prompt

    await websocket.accept()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        await websocket.close()
        return

    REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-realtime-1.5"
    stream_sid = None
    audio_buffer = []

    import logging
    logger = logging.getLogger("call_bridge")

    def execute_tool(name: str, args: dict) -> str:
        from agent.agent import ClinicAgent
        agent = ClinicAgent(db=db)
        return agent._execute_tool(name, args)

    try:
        logger.warning("🔌 Conectando a OpenAI Realtime API...")
        async with ws_lib.connect(
            REALTIME_URL,
            additional_headers={
                "Authorization": f"Bearer {api_key}"
            }
        ) as openai_ws:
            logger.warning("✅ OpenAI Realtime conectado")

            # Configurar sesión — formato oficial Twilio + OpenAI Realtime
            await openai_ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "output_modalities": ["audio"],
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcmu"},
                            "turn_detection": {
                                    "type": "server_vad",
                                    "silence_duration_ms": 2000,
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
            }))

            # Disparar saludo inicial
            await openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Saluda al paciente."}]
                }
            }))
            await openai_ws.send(json.dumps({"type": "response.create"}))

            async def twilio_to_openai():
                nonlocal stream_sid
                try:
                    async for raw in websocket.iter_text():
                        data = json.loads(raw)
                        event = data.get("event")

                        if event == "start":
                            stream_sid = data["start"]["streamSid"]
                            logger.warning(f"📞 Stream iniciado: {stream_sid}")

                        elif event == "media" and stream_sid:
                            await openai_ws.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": data["media"]["payload"]
                            }))

                        elif event == "stop":
                            break
                except WebSocketDisconnect:
                    pass
                finally:
                    await openai_ws.close()

            async def openai_to_twilio():
                try:
                    async for raw in openai_ws:
                        msg = json.loads(raw)
                        mtype = msg.get("type", "")
                        # Log todos los eventos excepto audio (demasiado verboso)
                        if "audio.delta" not in mtype:
                            logger.warning(f"📨 OpenAI evento: {mtype} | {json.dumps(msg)[:200]}")

                        # Audio → Twilio (con buffer si stream_sid aún no llegó)
                        if mtype == "response.output_audio.delta":
                            delta = msg.get("delta", "")
                            if stream_sid:
                                for buffered in audio_buffer:
                                    await websocket.send_json({
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {"payload": buffered}
                                    })
                                audio_buffer.clear()
                                await websocket.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": delta}
                                })
                            else:
                                audio_buffer.append(delta)

                        # Interrupción del paciente → limpiar buffer de audio
                        elif mtype == "input_audio_buffer.speech_started" and stream_sid:
                            await websocket.send_json({
                                "event": "clear",
                                "streamSid": stream_sid
                            })

                        # Tool call completado → ejecutar y devolver resultado
                        elif mtype == "response.function_call_arguments.done":
                            fn_name = msg.get("name", "")
                            call_id = msg.get("call_id", "")
                            try:
                                args = json.loads(msg.get("arguments", "{}"))
                                result = execute_tool(fn_name, args)
                            except Exception as e:
                                result = json.dumps({"error": str(e)})

                            await openai_ws.send(json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": result
                                }
                            }))
                            await openai_ws.send(json.dumps({"type": "response.create"}))

                except Exception:
                    pass
                finally:
                    try:
                        await websocket.close()
                    except Exception:
                        pass

            await asyncio.gather(twilio_to_openai(), openai_to_twilio())

    except Exception as e:
        logger.error(f"❌ ERROR en bridge de llamada: {type(e).__name__}: {e}")
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, db: Session = Depends(get_db)):
    """WebSocket para el chat con el agente IA."""
    await websocket.accept()

    conversation_history = []

    # Mensaje de bienvenida
    await websocket.send_json({
        "type": "bot",
        "message": "¡Hola! 👋 Soy el asistente virtual de la Clínica Dental Demo.\n\nPuedo ayudarte a:\n• Consultar disponibilidad de doctores\n• Pedir o cancelar una cita\n• Ver tus próximas citas\n\n¿En qué puedo ayudarte hoy?"
    })

    try:
        while True:
            data = await websocket.receive_json()
            user_msg = data.get("message", "").strip()
            if not user_msg:
                continue

            from agent.agent import ClinicAgent
            agent = ClinicAgent(db=db, conversation_history=conversation_history)
            response = await agent.chat(user_msg)
            conversation_history = agent.conversation_history

            await websocket.send_json({"type": "bot", "message": response})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "bot",
                "message": f"Ha ocurrido un error inesperado. Por favor, recarga la página."
            })
        except Exception:
            pass


@app.post("/seed", tags=["Sistema"], summary="Poblar BD con datos de demo")
def seed_database(db: Session = Depends(get_db)):
    """Ejecuta el seed de datos de demo. Borra los datos existentes primero."""
    from seed_data import run_seed
    run_seed(db)
    return {"mensaje": "Base de datos poblada con datos de demo correctamente"}
