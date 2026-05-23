"""
Definiciones de herramientas compartidas entre el agente de chat y el de voz.
Fuente única de verdad — cualquier herramienta nueva se añade SOLO aquí.
"""

# Formato OpenAI Chat Completions (usado por agent.py)
CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "listar_doctores",
            "description": "Lista todos los doctores disponibles con sus especialidades e IDs"
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_tipos_cita",
            "description": "Lista los tipos de cita disponibles con duración e IDs"
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_disponibilidad",
            "description": "Consulta los huecos disponibles de un doctor para una fecha y tipo de cita concretos",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer", "description": "ID del doctor"},
                    "appointment_type_id": {"type": "integer", "description": "ID del tipo de cita"},
                    "fecha": {"type": "string", "description": "Fecha en formato YYYY-MM-DD"}
                },
                "required": ["doctor_id", "appointment_type_id", "fecha"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_paciente",
            "description": "Busca un paciente por número de teléfono",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Número de teléfono del paciente"}
                },
                "required": ["phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_paciente",
            "description": "Registra un nuevo paciente en el sistema",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string", "description": "Opcional"}
                },
                "required": ["name", "phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_cita",
            "description": "Crea una cita para el paciente. Siempre confirma los detalles antes de llamar esta función.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "integer"},
                    "doctor_id": {"type": "integer"},
                    "appointment_type_id": {"type": "integer"},
                    "start_datetime": {"type": "string", "description": "ISO format: 2025-01-15T09:00:00"},
                    "notes": {"type": "string", "description": "Notas opcionales"}
                },
                "required": ["patient_id", "doctor_id", "appointment_type_id", "start_datetime"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_citas_paciente",
            "description": "Ver las citas próximas de un paciente",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "integer"}
                },
                "required": ["patient_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancelar_cita",
            "description": "Cancela una cita existente. Verifica que la cita pertenece al paciente antes de cancelar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer"},
                    "patient_id": {"type": "integer", "description": "ID del paciente que solicita la cancelación"}
                },
                "required": ["appointment_id", "patient_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_citas_del_dia",
            "description": "Lista todas las citas programadas para una fecha concreta. Úsala cuando alguien pregunte qué citas hay un día, cuántas citas hay, o quiera ver la agenda del día.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string", "description": "Fecha en formato YYYY-MM-DD"}
                },
                "required": ["fecha"]
            }
        }
    }
]


def _extract_realtime_tools():
    """
    Convierte CHAT_TOOLS al formato OpenAI Realtime API.
    Realtime usa {type, name, description, parameters} sin wrapper "function".
    """
    realtime = []
    for tool in CHAT_TOOLS:
        fn = tool["function"]
        entry = {
            "type": "function",
            "name": fn["name"],
            "description": fn["description"],
        }
        if "parameters" in fn:
            entry["parameters"] = fn["parameters"]
        realtime.append(entry)
    return realtime


REALTIME_TOOLS = _extract_realtime_tools()
