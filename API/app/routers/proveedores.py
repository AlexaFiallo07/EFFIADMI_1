from fastapi import APIRouter, Depends, HTTPException, status

from ..database import get_db, to_dict, to_object_id
from ..schemas import Proveedor, ProveedorUpdate
from ..security import get_current_user

router = APIRouter(prefix="/api/proveedores", tags=["Proveedores"])


def limpiar_datos(data: dict):
    return {k: v for k, v in data.items() if v is not None}


@router.get("")
async def listar_proveedores(db=Depends(get_db), usuario=Depends(get_current_user)):
    proveedores = []
    cursor = db.proveedores.find().sort("nombre_proveedor", 1)
    async for proveedor in cursor:
        proveedores.append(to_dict(proveedor))
    return {"data": proveedores, "total": len(proveedores)}


@router.get("/{proveedor_id}")
async def obtener_proveedor(proveedor_id: str, db=Depends(get_db), usuario=Depends(get_current_user)):
    object_id = to_object_id(proveedor_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de proveedor no válido")
    proveedor = await db.proveedores.find_one({"_id": object_id})
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return to_dict(proveedor)


@router.post("", status_code=status.HTTP_201_CREATED)
async def crear_proveedor(data: Proveedor, db=Depends(get_db), usuario=Depends(get_current_user)):
    result = await db.proveedores.insert_one(data.model_dump())
    creado = await db.proveedores.find_one({"_id": result.inserted_id})
    return to_dict(creado)


@router.put("/{proveedor_id}")
async def actualizar_proveedor(
    proveedor_id: str, data: ProveedorUpdate, db=Depends(get_db), usuario=Depends(get_current_user)
):
    object_id = to_object_id(proveedor_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de proveedor no válido")
    cambios = limpiar_datos(data.model_dump())
    resultado = await db.proveedores.update_one({"_id": object_id}, {"$set": cambios})
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    actualizado = await db.proveedores.find_one({"_id": object_id})
    return to_dict(actualizado)


@router.delete("/{proveedor_id}")
async def eliminar_proveedor(proveedor_id: str, db=Depends(get_db), usuario=Depends(get_current_user)):
    object_id = to_object_id(proveedor_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de proveedor no válido")
    resultado = await db.proveedores.delete_one({"_id": object_id})
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return {"message": "Proveedor eliminado correctamente"}
