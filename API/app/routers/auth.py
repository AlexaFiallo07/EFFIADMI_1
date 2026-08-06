from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from ..database import get_db, to_dict
from ..schemas import UsuarioLogin, UsuarioRegister
from ..security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: UsuarioRegister, db=Depends(get_db)):
    email_existente = await db.usuarios.find_one({"email": data.email.lower()})
    if email_existente:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo")

    usuario = {
        "nombre_usuario": data.nombre_usuario,
        "apellido_usuario": data.apellido_usuario,
        "email": data.email.lower(),
        "contraseña": hash_password(data.contraseña),
        "cargo": data.cargo,
        "fecha_registro": datetime.now(timezone.utc),
    }
    result = await db.usuarios.insert_one(usuario)
    creado = await db.usuarios.find_one({"_id": result.inserted_id})
    return to_dict(creado)


@router.post("/login")
async def login(data: UsuarioLogin, db=Depends(get_db)):
    usuario = await db.usuarios.find_one({"email": data.email.lower()})
    if not usuario or not verify_password(data.contraseña, usuario["contraseña"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    token = create_access_token(str(usuario["_id"]))
    usuario_dict = to_dict(usuario)
    usuario_dict.pop("contraseña", None)
    return {"access_token": token, "token_type": "bearer", "usuario": usuario_dict}


@router.get("/me")
async def me(usuario=Depends(get_current_user)):
    return usuario
