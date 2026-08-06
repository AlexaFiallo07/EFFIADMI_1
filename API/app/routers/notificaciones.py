from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from ..database import get_db, to_dict, to_object_id
from ..schemas import NotificacionCreate, NotificacionUpdate
from ..security import get_current_user

router = APIRouter(prefix="/api/notificaciones", tags=["Notificaciones"])


@router.get("")
async def listar_notificaciones(db=Depends(get_db), usuario=Depends(get_current_user)):
    notificaciones = []
    cursor = db.notificaciones.find().sort("fecha_creacion", -1).limit(100)
    async for notificacion in cursor:
        notificaciones.append(to_dict(notificacion))
    no_leidas = sum(1 for n in notificaciones if not n["leido"])
    return {"data": notificaciones, "total": len(notificaciones), "no_leidas": no_leidas}


@router.get("/{notificacion_id}")
async def obtener_notificacion(notificacion_id: str, db=Depends(get_db), usuario=Depends(get_current_user)):
    object_id = to_object_id(notificacion_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de notificación no válido")
    notificacion = await db.notificaciones.find_one({"_id": object_id})
    if not notificacion:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return to_dict(notificacion)


@router.post("", status_code=status.HTTP_201_CREATED)
async def crear_notificacion(data: NotificacionCreate, db=Depends(get_db), usuario=Depends(get_current_user)):
    notificacion = {
        "mensaje": data.mensaje,
        "fecha_creacion": datetime.now(timezone.utc),
        "leido": False,
    }
    result = await db.notificaciones.insert_one(notificacion)
    creada = await db.notificaciones.find_one({"_id": result.inserted_id})
    return to_dict(creada)


@router.put("/{notificacion_id}")
async def actualizar_notificacion(
    notificacion_id: str, data: NotificacionUpdate, db=Depends(get_db), usuario=Depends(get_current_user)
):
    object_id = to_object_id(notificacion_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de notificación no válido")
    resultado = await db.notificaciones.update_one(
        {"_id": object_id}, {"$set": data.model_dump(exclude_none=True)}
    )
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    actualizada = await db.notificaciones.find_one({"_id": object_id})
    return to_dict(actualizada)


@router.delete("/{notificacion_id}")
async def eliminar_notificacion(notificacion_id: str, db=Depends(get_db), usuario=Depends(get_current_user)):
    object_id = to_object_id(notificacion_id)
    if object_id is None:
        raise HTTPException(status_code=400, detail="Id de notificación no válido")
    resultado = await db.notificaciones.delete_one({"_id": object_id})
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return {"message": "Notificación eliminada correctamente"}
