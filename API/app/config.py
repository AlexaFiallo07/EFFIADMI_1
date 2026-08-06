import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "effiadmi")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")


settings = Settings()
