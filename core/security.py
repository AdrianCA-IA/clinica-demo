"""
Seguridad: autenticación admin y rate limiting.
"""

import os
import time
from collections import defaultdict
from fastapi import HTTPException, Depends, Request
from fastapi.security import APIKeyHeader

# ── Admin API Key ────────────────────────────────────────────────────────────
# Protege endpoints sensibles (seed, llamadas salientes, etc.)
# Se configura en .env como ADMIN_API_KEY

_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def require_admin(api_key: str = Depends(_api_key_header)):
    """Dependencia para endpoints que requieren autenticación admin."""
    expected = os.getenv("ADMIN_API_KEY")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_API_KEY no configurada en .env. Configúrala para usar este endpoint."
        )
    if not api_key or api_key != expected:
        raise HTTPException(status_code=403, detail="API key inválida o no proporcionada")


# ── Rate Limiter simple (en memoria) ────────────────────────────────────────
# Para producción real, usar Redis (ej: slowapi + redis)

class RateLimiter:
    """
    Rate limiter por IP con ventana deslizante.
    Limita el número de peticiones por IP en un intervalo de tiempo.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, client_id: str) -> bool:
        """Retorna True si la petición está permitida, False si se excede el límite."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Limpiar timestamps antiguos
        self._requests[client_id] = [
            t for t in self._requests[client_id] if t > cutoff
        ]

        if len(self._requests[client_id]) >= self.max_requests:
            return False

        self._requests[client_id].append(now)
        return True

    def cleanup(self):
        """Limpia entradas expiradas para evitar memory leak."""
        now = time.time()
        cutoff = now - self.window_seconds
        expired = [k for k, v in self._requests.items() if all(t <= cutoff for t in v)]
        for k in expired:
            del self._requests[k]


# Instancia global — 30 mensajes por minuto por IP en WebSocket
ws_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)

# Instancia para API REST — 60 peticiones por minuto por IP
api_rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
