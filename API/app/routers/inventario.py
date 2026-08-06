from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, to_dict
from ..security import get_current_user

router = APIRouter(prefix="/api/inventario", tags=["Inventario"])


@router.get("")
async def inventario_actual(db=Depends(get_db), usuario=Depends(get_current_user)):
    productos = []
    async for producto in db.productos.find().sort("nombre_producto", 1):
        productos.append(to_dict(producto))
    valor_total = sum(p["precio_compra"] * p["stock_actual"] for p in productos)
    return {"data": productos, "total_productos": len(productos), "valor_inventario": valor_total}


@router.get("/bajo-stock")
async def inventario_bajo_stock(db=Depends(get_db), usuario=Depends(get_current_user)):
    productos_bajos = []
    async for producto in db.productos.find(
        {"$expr": {"$lt": ["$stock_actual", "$stock_minimo"]}}
    ):
        productos_bajos.append(to_dict(producto))
    return {"data": productos_bajos, "total": len(productos_bajos), "mensaje": "Productos que requieren reposición"}


@router.get("/resumen")
async def resumen_inventario(db=Depends(get_db), usuario=Depends(get_current_user)):
    total_productos = await db.productos.count_documents({})
    unidades_totales = 0
    valor_inventario = 0
    async for producto in db.productos.find({}):
        unidades_totales += producto["stock_actual"]
        valor_inventario += producto["precio_compra"] * producto["stock_actual"]
    return {
        "total_productos": total_productos,
        "unidades_totales": unidades_totales,
        "valor_inventario": valor_inventario,
    }
