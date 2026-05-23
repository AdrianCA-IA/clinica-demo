"""
Script ONE-TIME para obtener el refresh token de Google Calendar.
Ejecuta este script UNA VEZ, copia el refresh token al .env, y ya no lo necesitas más.

Uso:
    python get_google_token.py
"""
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CLIENT_FILE = os.path.join(os.path.dirname(__file__), "credentials", "google-oauth-client.json")

def main():
    if not os.path.exists(CLIENT_FILE):
        print(f"❌ No se encontró el fichero: {CLIENT_FILE}")
        print("   Asegúrate de haber copiado el JSON de Google Cloud a credentials/google-oauth-client.json")
        return

    print("🔐 Abriendo navegador para autorizar Google Calendar...")
    print("   Inicia sesión con la cuenta que tiene acceso al calendario de la clínica.\n")

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    print("\n✅ ¡Autorización completada!\n")
    print("=" * 60)
    print("Añade estas líneas a tu fichero .env:")
    print("=" * 60)
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print(f"GOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    print("=" * 60)
    print("\nTambién necesitas el GOOGLE_CALENDAR_ID.")
    print("Encuéntralo en Google Calendar → ajustes del calendario → 'ID del calendario'")
    print("Si es tu calendario principal usa: primary")

if __name__ == "__main__":
    main()
