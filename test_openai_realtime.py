"""
Test rápido de conexión a OpenAI Realtime API.
Ejecutar: python test_openai_realtime.py
"""
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def test_realtime():
    try:
        import websockets
    except ImportError:
        print("❌ Falta el paquete websockets: pip install websockets")
        return

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY no está en el .env")
        return

    model = "gpt-realtime-1.5"
    url = f"wss://api.openai.com/v1/realtime?model={model}"

    print(f"🔌 Conectando a OpenAI Realtime API...")
    print(f"   Modelo: {model}")
    print(f"   URL: {url}")
    print()

    try:
        async with websockets.connect(
            url,
            additional_headers={"Authorization": f"Bearer {api_key}"},
            open_timeout=10
        ) as ws:
            print("✅ Conexión establecida con OpenAI Realtime")

            # Escuchar el primer mensaje (session.created)
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            print(f"✅ Primer mensaje recibido: type={data.get('type')}")

            if data.get("type") == "session.created":
                session = data.get("session", {})
                print(f"   session_id: {session.get('id', 'N/A')}")
                print(f"   model: {session.get('model', 'N/A')}")
                print()
                print("✅ OpenAI Realtime API funciona correctamente")
            else:
                print(f"   Mensaje completo: {json.dumps(data, indent=2)}")

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Error HTTP {e.status_code}: {e}")
        if e.status_code == 401:
            print("   → API key inválida o sin permisos para Realtime API")
        elif e.status_code == 404:
            print(f"   → Modelo '{model}' no encontrado")
            print("   → Prueba con: gpt-4o-realtime-preview")
        elif e.status_code == 429:
            print("   → Rate limit o créditos insuficientes")
    except asyncio.TimeoutError:
        print("❌ Timeout — OpenAI no respondió en 5 segundos")
        print("   → Comprueba la conexión a internet")
    except Exception as e:
        print(f"❌ Error inesperado: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_realtime())
