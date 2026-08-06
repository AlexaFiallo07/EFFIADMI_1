from fastapi import APIRouter, Depends

from ..database import get_db
from ..security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/estadisticas")
async def estadisticas(db=Depends(get_db), usuario=Depends(get_current_user)):
    total_productos = await db.productos.count_documents({})
    total_proveedores = await db.proveedores.count_documents({})
    total_usuarios = await db.usuarios.count_documents({})

    valor_inventario = 0
    unidades_totales = 0
    productos_bajos = []
    async for producto in db.productos.find({}):
        unidades_totales += producto["stock_actual"]
        valor_inventario += producto["precio_compra"] * producto["stock_actual"]
        if producto["stock_actual"] < producto["stock_minimo"]:
            productos_bajos.append(
                {
                    "id": str(producto["_id"]),
                    "nombre_producto": producto["nombre_producto"],
                    "stock_actual": producto["stock_actual"],
                    "stock_minimo": producto["stock_minimo"],
                }
            )

    producto_mas_vendido = None
    ventas_por_producto = {}
    async for movimiento in db.movimientos.find({"tipo": "salida"}):
        clave = movimiento.get("producto_id") or movimiento.get("nombre_producto")
        ventas_por_producto[clave] = ventas_por_producto.get(clave, 0) + movimiento["cantidad"]
    if ventas_por_producto:
        top_id = max(ventas_por_producto, key=ventas_por_producto.get)
        top_movimiento = await db.movimientos.find_one({"producto_id": top_id})
        producto_mas_vendido = {
            "producto_id": top_id,
            "nombre_producto": top_movimiento.get("nombre_producto", "Sin nombre"),
            "unidades_vendidas": ventas_por_producto[top_id],
        }

    entradas = await db.movimientos.count_documents({"tipo": "entrada"})
    salidas = await db.movimientos.count_documents({"tipo": "salida"})

    return {
        "totales": {
            "productos": total_productos,
            "proveedores": total_proveedores,
            "usuarios": total_usuarios,
        },
        "inventario": {
            "unidades_totales": unidades_totales,
            "valor_inventario": valor_inventario,
            "productos_bajo_stock": len(productos_bajos),
        },
        "movimientos": {"entradas": entradas, "salidas": salidas},
        "producto_mas_vendido": producto_mas_vendido,
        "reposicion_sugerida": productos_bajos,
    }
