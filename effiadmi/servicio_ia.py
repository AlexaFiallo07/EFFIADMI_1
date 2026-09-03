import os
from openai import OpenAI
from dotenv import load_dotenv

# Esto busca el archivo .env automáticamente
load_dotenv()

# Cliente de Gemini (gratis) usando el endpoint compatible con OpenAI.
# Se inicializa solo cuando se usa (para no romper la app si falta la clave).
_client = None

_SYSTEM_PROMPT = (
    "Eres el asistente inteligente de EFFIADMI. Ayudas a gestionar inventarios, "
    "ventas y atención al cliente para pymes."
)

def _obtener_cliente():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return _client

def _formatear_contexto(contexto_negocio):
    if not contexto_negocio:
        return ""
    lineas = [
        "A continuacion tienes los datos actuales del negocio (inventario, ventas, proveedores).",
        "Usa estos datos reales para responder. Si te piden evaluar rentabilidad, "
        "basate en las unidades vendidas y el margen (precio_venta - precio_compra) cuando este disponible. "
        "Si te piden generar un correo a un proveedor, redacta un borrador con asunto y cuerpo listo para copiar.",
    ]
    for clave, valor in contexto_negocio.items():
        lineas.append(f"- {clave}: {valor}")
    return "\n".join(lineas)

def consultar_asistente_effiadmi(mensaje_usuario, contexto_negocio=None):
    try:
        if not os.getenv("GEMINI_API_KEY"):
            return "No hay clave de Gemini. Agrega GEMINI_API_KEY en el archivo .env (crea una gratis en aistudio.google.com/apikey)."
        system_content = _SYSTEM_PROMPT
        if contexto_negocio:
            system_content += "\n\n" + _formatear_contexto(contexto_negocio)
        respuesta = _obtener_cliente().chat.completions.create(
            model="gemini-3.1-flash-lite",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": mensaje_usuario}
            ]
        )
        return respuesta.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"
