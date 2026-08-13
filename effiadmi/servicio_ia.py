import os
from openai import OpenAI
from dotenv import load_dotenv

# Esto busca el archivo .env automáticamente
load_dotenv()

# Cliente de Gemini (gratis) usando el endpoint compatible con OpenAI.
# Se inicializa solo cuando se usa (para no romper la app si falta la clave).
_client = None

def _obtener_cliente():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return _client

def consultar_asistente_effiadmi(mensaje_usuario):
    try:
        if not os.getenv("GEMINI_API_KEY"):
            return "No hay clave de Gemini. Agrega GEMINI_API_KEY en el archivo .env (crea una gratis en aistudio.google.com/apikey)."
        respuesta = _obtener_cliente().chat.completions.create(
            model="gemini-3.1-flash-lite",
            messages=[
                {"role": "system", "content": "Eres el asistente inteligente de EFFIADMI. Ayudas a gestionar inventarios, ventas y atención al cliente para pymes."},
                {"role": "user", "content": mensaje_usuario}
            ]
        )
        return respuesta.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"
