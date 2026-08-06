from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings

client = AsyncIOMotorClient(settings.MONGODB_URI)
db = client[settings.DATABASE_NAME]


def get_db():
    return db


def to_dict(document):
    if document is None:
        return None
    document = dict(document)
    document["id"] = str(document.pop("_id"))
    return document


def to_object_id(value):
    try:
        return ObjectId(value)
    except Exception:
        return None


async def create_indexes():
    await db.usuarios.create_index([("email", 1)], unique=True)
    await db.productos.create_index([("nombre_producto", 1)])
    await db.movimientos.create_index([("fecha", -1)])
