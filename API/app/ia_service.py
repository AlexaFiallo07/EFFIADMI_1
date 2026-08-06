from openai import OpenAI

from .config import settings

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def consultar_asistente(mensaje_usuario: str) -> str:
    try:
        respuesta = get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres el asistente inteligente de EFFIADMI. Ayudas a gestionar "
                        "inventarios, ventas y atención al cliente para pymes. "
                        "Responde en español, de forma breve y práctica."
                    ),
                },
                {"role": "user", "content": mensaje_usuario},
            ],
        )
        return respuesta.choices[0].message.content
    except Exception as error:
        return f"Error al consultar el asistente: {str(error)}"
