import asyncio
from datetime import datetime, timezone

from app.config import settings
from app.database import db
from app.security import hash_password

PRODUCTOS = [
    {"nombre_producto": "Arroz blanco 1kg", "descripcion": "Arroz blanco en bolsa de 1 kilogramo", "precio_venta": 4200, "precio_compra": 3000, "stock_actual": 80, "stock_minimo": 30},
    {"nombre_producto": "Aceite vegetal 500ml", "descripcion": "Aceite vegetal en botella de 500ml", "precio_venta": 9800, "precio_compra": 7200, "stock_actual": 25, "stock_minimo": 20},
    {"nombre_producto": "Azúcar refinada 1kg", "descripcion": "Azúcar refinada en bolsa de 1 kilogramo", "precio_venta": 5100, "precio_compra": 3800, "stock_actual": 15, "stock_minimo": 25},
    {"nombre_producto": "Café molido 250g", "descripcion": "Café molido en empaque de 250 gramos", "precio_venta": 14500, "precio_compra": 11200, "stock_actual": 40, "stock_minimo": 15},
    {"nombre_producto": "Panela 1kg", "descripcion": "Panela entera de 1 kilogramo", "precio_venta": 6200, "precio_compra": 4500, "stock_actual": 8, "stock_minimo": 20},
]

PROVEEDORES = [
    {"nombre_proveedor": "Distribuidora La Gran Colombia", "correo": "ventas@grancolombia.com", "telefono": "3101112233", "direccion": "Carrera 12 # 45-20, Bogotá"},
    {"nombre_proveedor": "Agroinsumos del Campo", "correo": "pedidos@agrocampo.com", "telefono": "3204455667", "direccion": "Calle 8 # 15-60, Medellín"},
]

USUARIOS = [
    {
        "nombre_usuario": "Admin",
        "apellido_usuario": "EFFIADMI",
        "email": "admin@effiadmi.com",
        "contraseña": "admin123",
        "cargo": "Admin",
        "fecha_registro": datetime.now(timezone.utc),
    },
]


async def cargar_datos():
    print("Conectando a", settings.MONGODB_URI.split("//")[1].split("/")[0] if "//" in settings.MONGODB_URI else settings.MONGODB_URI)

    total_productos = await db.productos.count_documents({})
    if total_productos == 0:
        for producto in PRODUCTOS:
            producto["fecha_creacion"] = datetime.now(timezone.utc)
        await db.productos.insert_many(PRODUCTOS)
        print(f"Se insertaron {len(PRODUCTOS)} productos de ejemplo")
    else:
        print(f"Ya existen {total_productos} productos, no se insertan duplicados")

    total_proveedores = await db.proveedores.count_documents({})
    if total_proveedores == 0:
        await db.proveedores.insert_many(PROVEEDORES)
        print(f"Se insertaron {len(PROVEEDORES)} proveedores de ejemplo")
    else:
        print("Ya existen proveedores, no se insertan duplicados")

    total_usuarios = await db.usuarios.count_documents({})
    if total_usuarios == 0:
        usuarios_listos = []
        for usuario in USUARIOS:
            copia = dict(usuario)
            copia["contraseña"] = hash_password(usuario["contraseña"])
            usuarios_listos.append(copia)
        await db.usuarios.insert_many(usuarios_listos)
        print("Se insertó el usuario administrador de ejemplo (admin@effiadmi.com / admin123)")
    else:
        print("Ya existen usuarios, no se insertan duplicados")


if __name__ == "__main__":
    asyncio.run(cargar_datos())
