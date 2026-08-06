import os
from openai import OpenAI
from dotenv import load_dotenv

# Esto busca el archivo .env automáticamente
load_dotenv()

# Inicializa la conexión
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def consultar_asistente_effiadmi(mensaje_usuario):
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres el asistente inteligente de EFFIADMI. Ayudas a gestionar inventarios, ventas y atención al cliente para pymes."},
                {"role": "user", "content": mensaje_usuario}
            ]
        )
        return respuesta.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"