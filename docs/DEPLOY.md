# 🚀 Guía de Despliegue en Producción

Esta guía explica cómo desplegar Clínica Demo en un servidor VPS con Ubuntu 22.04.

---

## Requisitos del servidor

- Ubuntu 22.04 LTS (o similar)
- 1 GB RAM mínimo (recomendado 2 GB)
- 10 GB de disco
- Python 3.10+
- Un dominio o subdominio apuntando al servidor

---

## 1. Preparar el servidor

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git nginx -y
```

---

## 2. Clonar el proyecto

```bash
cd /opt
sudo git clone https://github.com/tu-usuario/clinica-demo.git
sudo chown -R $USER:$USER /opt/clinica-demo
cd /opt/clinica-demo
```

---

## 3. Entorno virtual y dependencias

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Variables de entorno

```bash
cp .env.example .env
nano .env   # rellenar con las credenciales reales
```

Variables críticas en producción:
- `DATABASE_URL` — Cambiar a PostgreSQL si se espera mucha carga (ver sección al final)
- `OPENAI_API_KEY` — Clave de producción con límites de gasto configurados
- `TWILIO_AUTH_TOKEN` — Rotar si fue expuesto en algún momento

---

## 5. Preparar la base de datos

```bash
source venv/bin/activate
python seed_data.py
python migrate_add_gcal.py
```

---

## 6. Servicio systemd (arranque automático)

Crea el archivo de servicio:

```bash
sudo nano /etc/systemd/system/clinica.service
```

Contenido:

```ini
[Unit]
Description=Clinica Demo - Asistente IA de Citas
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/clinica-demo
Environment="PATH=/opt/clinica-demo/venv/bin"
ExecStart=/opt/clinica-demo/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Activar y arrancar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clinica
sudo systemctl start clinica
sudo systemctl status clinica   # verificar que está corriendo
```

---

## 7. Nginx como reverse proxy

```bash
sudo nano /etc/nginx/sites-available/clinica
```

Contenido:

```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
```

Activar y recargar:

```bash
sudo ln -s /etc/nginx/sites-available/clinica /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL con Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d tu-dominio.com
```

---

## 8. Alternativa: Cloudflare Tunnel (más simple, sin SSL manual)

Si prefieres evitar la configuración de Nginx y SSL:

```bash
# Instalar cloudflared
curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared -y

# Autenticar
cloudflared tunnel login

# Crear túnel permanente
cloudflared tunnel create clinica-demo
cloudflared tunnel route dns clinica-demo tu-dominio.com

# Configurar como servicio
cloudflared service install
```

---

## 9. Configurar Twilio en producción

Una vez el servidor esté accesible públicamente:

1. Ir a Twilio Console → Phone Numbers → Tu número
2. Voice → Webhook: `https://tu-dominio.com/twilio/voice`
3. Método: HTTP POST
4. Guardar

---

## 10. Verificación final

```bash
# Ver logs del servicio
sudo journalctl -u clinica -f

# Probar que responde
curl https://tu-dominio.com/docs

# Probar chat
# Abrir https://tu-dominio.com/chat en el navegador
```

---

## Migración a PostgreSQL (opcional, recomendada para producción)

```bash
sudo apt install postgresql postgresql-contrib -y
sudo -u postgres createuser clinica_user
sudo -u postgres createdb clinica_db -O clinica_user
sudo -u postgres psql -c "ALTER USER clinica_user WITH PASSWORD 'tu_password_seguro';"
pip install psycopg2-binary
```

Cambiar en `.env`:
```
DATABASE_URL=postgresql://clinica_user:tu_password@localhost/clinica_db
```

Regenerar tablas:
```bash
python seed_data.py
python migrate_add_gcal.py
```

---

## Actualizaciones del código

```bash
cd /opt/clinica-demo
git pull origin main
source venv/bin/activate
pip install -r requirements.txt   # si hay paquetes nuevos
sudo systemctl restart clinica
```
