from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from ..database import get_db, to_dict, to_object_id
from ..schemas import Movimiento
from ..security import get_current_user
from ..ws_manager import ws_manager

router = APIRouter(prefix="/api/movimientos", tags=["Movimientos"])

TIPOS_VALIDOS = ["entrada", "salida", "ajuste"]


@router.get("")
async def listar_movimientos(db=Depends(get_db), usuario=Depends(get_current_user)):
    movimientos = []
    cursor = db.movimientos.find().sort("fecha", -1).limit(200)
    async for movimiento in cursor:
        movimientos.append(to_dict(movimiento))
    return {"data": movimientos, "total": len(movimientos)}


@router.get("/{movimiento_id}")
async def obtener_movimiento(movimiento_id: str, db=Depends(get_db), usuario=Depends(get_current_user)):
    object_id = to_object_id(movimiento_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de movimiento no válido")
    movimiento = await db.movimientos.find_one({"_id": object_id})
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return to_dict(movimiento)


@router.post("", status_code=status.HTTP_201_CREATED)
async def registrar_movimiento(data: Movimiento, db=Depends(get_db), usuario=Depends(get_current_user)):
    if data.tipo not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=400, detail=f"Tipo no válido. Debe ser uno de: {', '.join(TIPOS_VALIDOS)}"
        )
    if data.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a cero")

    producto_id = to_object_id(data.producto_id)
    if producto_id is None:
        raise HTTPException(status_code=400, detail="Id de producto no válido")

    producto = await db.productos.find_one({"_id": producto_id})
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    stock_actual = producto["stock_actual"]

    if data.tipo == "entrada":
        nuevo_stock = stock_actual + data.cantidad
    elif data.tipo == "salida":
        if stock_actual < data.cantidad:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente. Stock actual: {stock_actual}",
            )
        nuevo_stock = stock_actual - data.cantidad
    else:
        nuevo_stock = data.cantidad

    await db.productos.update_one({"_id": producto_id}, {"$set": {"stock_actual": nuevo_stock}})

    movimiento = {
        "producto_id": data.producto_id,
        "nombre_producto": producto["nombre_producto"],
        "tipo": data.tipo,
        "cantidad": data.cantidad,
        "descripcion": data.descripcion,
        "usuario_id": usuario["id"],
        "fecha": datetime.now(timezone.utc),
    }
    result = await db.movimientos.insert_one(movimiento)
    movimiento["id"] = str(result.inserted_id)

    if nuevo_stock < producto["stock_minimo"]:
        notificacion = {
            "mensaje": (
                f"El producto '{producto['nombre_producto']}' está por debajo del stock "
                f"mínimo: {nuevo_stock}/{producto['stock_minimo']}"
            ),
            "fecha_creacion": datetime.now(timezone.utc),
            "leido": False,
        }
        await db.notificaciones.insert_one(notificacion)

    await ws_manager.broadcast(
        {
            "evento": "movimiento_inventario",
            "producto_id": data.producto_id,
            "nombre_producto": producto["nombre_producto"],
            "tipo": data.tipo,
            "cantidad": data.cantidad,
            "stock_actual": nuevo_stock,
        }
    )

    return to_dict(movimiento)
