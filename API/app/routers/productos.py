from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from ..database import get_db, to_dict, to_object_id
from ..schemas import Producto, ProductoUpdate
from ..security import get_current_user

router = APIRouter(prefix="/api/productos", tags=["Productos"])


def limpiar_datos(data: dict):
    return {k: v for k, v in data.items() if v is not None}


@router.get("")
async def listar_productos(db=Depends(get_db), usuario=Depends(get_current_user)):
    productos = []
    cursor = db.productos.find().sort("nombre_producto", 1)
    async for producto in cursor:
        productos.append(to_dict(producto))
    return {"data": productos, "total": len(productos)}


@router.get("/{producto_id}")
async def obtener_producto(producto_id: str, db=Depends(get_db), usuario=Depends(get_current_user)):
    object_id = to_object_id(producto_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de producto no válido")
    producto = await db.productos.find_one({"_id": object_id})
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return to_dict(producto)


@router.post("", status_code=status.HTTP_201_CREATED)
async def crear_producto(data: Producto, db=Depends(get_db), usuario=Depends(get_current_user)):
    producto = data.model_dump()
    producto["fecha_creacion"] = datetime.now(timezone.utc)
    result = await db.productos.insert_one(producto)
    creado = await db.productos.find_one({"_id": result.inserted_id})
    return to_dict(creado)


@router.put("/{producto_id}")
async def actualizar_producto(
    producto_id: str, data: ProductoUpdate, db=Depends(get_db), usuario=Depends(get_current_user)
):
    object_id = to_object_id(producto_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de producto no válido")
    cambios = limpiar_datos(data.model_dump())
    resultado = await db.productos.update_one({"_id": object_id}, {"$set": cambios})
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    actualizado = await db.productos.find_one({"_id": object_id})
    return to_dict(actualizado)


@router.delete("/{producto_id}")
async def eliminar_producto(producto_id: str, db=Depends(get_db), usuario=Depends(get_current_user)):
    object_id = to_object_id(producto_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de producto no válido")
    resultado = await db.productos.delete_one({"_id": object_id})
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"message": "Producto eliminado correctamente"}
