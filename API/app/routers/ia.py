from fastapi import APIRouter, Depends

from ..ia_service import consultar_asistente
from ..schemas import ChatRequest
from ..security import get_current_user

router = APIRouter(prefix="/api/ia", tags=["Asistente de IA"])


@router.post("/consultar")
async def consultar(data: ChatRequest, usuario=Depends(get_current_user)):
    respuesta = consultar_asistente(data.mensaje)
    return {"mensaje": data.mensaje, "respuesta": respuesta}
