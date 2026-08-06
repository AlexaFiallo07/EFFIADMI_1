from typing import Optional

from pydantic import BaseModel


class UsuarioRegister(BaseModel):
    nombre_usuario: str
    apellido_usuario: str
    email: str
    contraseña: str
    cargo: str = "Operador"


class UsuarioLogin(BaseModel):
    email: str
    contraseña: str


class UsuarioOut(BaseModel):
    id: str
    nombre_usuario: str
    apellido_usuario: str
    email: str
    cargo: str


class Producto(BaseModel):
    nombre_producto: str
    descripcion: str = ""
    precio_venta: float
    precio_compra: float = 0
    stock_actual: int = 0
    stock_minimo: int = 5


class ProductoUpdate(BaseModel):
    nombre_producto: Optional[str] = None
    descripcion: Optional[str] = None
    precio_venta: Optional[float] = None
    precio_compra: Optional[float] = None
    stock_actual: Optional[int] = None
    stock_minimo: Optional[int] = None


class Movimiento(BaseModel):
    producto_id: str
    tipo: str
    cantidad: int
    descripcion: str = ""


class Proveedor(BaseModel):
    nombre_proveedor: str
    correo: str = ""
    telefono: str = ""
    direccion: str = ""


class ProveedorUpdate(BaseModel):
    nombre_proveedor: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None


class NotificacionCreate(BaseModel):
    mensaje: str


class NotificacionUpdate(BaseModel):
    leido: Optional[bool] = None


class ChatRequest(BaseModel):
    mensaje: str
