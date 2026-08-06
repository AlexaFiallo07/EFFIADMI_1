from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_indexes
from app.routers import (
    auth,
    productos,
    inventario,
    movimientos,
    proveedores,
    notificaciones,
    dashboard,
    ia,
)
from app.ws_manager import ws_manager

app = FastAPI(
    title="EFFIADMI API",
    description="API de gestión de inventario en tiempo real con apoyo de inteligencia artificial",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await create_indexes()
    print("API EFFIADMI iniciada correctamente")


@app.on_event("shutdown")
async def shutdown():
    ws_manager.disconnect_all()


@app.get("/")
async def root():
    return {"message": "Bienvenido a la API de EFFIADMI - Inventario en tiempo real"}


@app.websocket("/ws/inventario")
async def websocket_inventario(websocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        ws_manager.disconnect(websocket)


app.include_router(auth.router)
app.include_router(productos.router)
app.include_router(inventario.router)
app.include_router(movimientos.router)
app.include_router(proveedores.router)
app.include_router(notificaciones.router)
app.include_router(dashboard.router)
app.include_router(ia.router)
