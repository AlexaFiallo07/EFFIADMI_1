from django.db import transaction
from django.db.models import Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from .models import (
    Branch,
    Cliente,
    Factura,
    FacturaDetalle,
    Inventory,
    InventoryLog,
    Notificacion,
    Pedido,
    PedidoDetalle,
    Product,
    Proveedor,
)
from .serializers import (
    BranchSerializer,
    ClienteSerializer,
    FacturaSerializer,
    InventoryLogSerializer,
    InventorySerializer,
    NotificacionSerializer,
    PedidoSerializer,
    ProductSerializer,
    ProveedorSerializer,
    StockAdjustSerializer,
)
from .servicio_ia import consultar_asistente_effiadmi


# ============================================================
# Branch
# ============================================================

class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all().order_by("id")
    serializer_class = BranchSerializer


# ============================================================
# Product (auto-creates Inventory on save)
# ============================================================

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("id")
    serializer_class = ProductSerializer


# ============================================================
# Inventory (ajustar-stock + kardex)
# ============================================================

class InventoryViewSet(viewsets.ModelViewSet):
    queryset = Inventory.objects.select_related("product", "branch").all().order_by("id")
    serializer_class = InventorySerializer

    @action(detail=False, methods=["post"], url_path="ajustar-stock")
    def ajustar_stock(self, request):
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            with transaction.atomic():
                inventory = (
                    Inventory.objects
                    .select_for_update()
                    .get(
                        product_id=data["product_id"],
                        branch_id=data["sucursal_id"],
                    )
                )

                cantidad = data["cantidad"]
                tipo = data["tipo_movimiento"]

                if tipo == InventoryLog.ENTRADA:
                    inventory.cantidad_disponible += cantidad
                elif tipo == InventoryLog.SALIDA:
                    if inventory.cantidad_disponible < cantidad:
                        raise ValidationError(
                            {
                                "detail": (
                                    f"Stock insuficiente. Disponible: "
                                    f"{inventory.cantidad_disponible}"
                                )
                            }
                        )
                    inventory.cantidad_disponible -= cantidad
                elif tipo == InventoryLog.AJUSTE:
                    inventory.cantidad_disponible = cantidad

                inventory.save()

                log = InventoryLog.objects.create(
                    inventory=inventory,
                    tipo_movimiento=tipo,
                    cantidad=cantidad,
                    cantidad_resultante=inventory.cantidad_disponible,
                    motivo=data.get("motivo", ""),
                    usuario=request.user if request.user.is_authenticated else None,
                )

        except Inventory.DoesNotExist:
            return Response(
                {"detail": "No existe inventario para ese producto en esa sucursal."},
                status=status.HTTP_404_NOT_FOUND,
            )

        alerta = inventory.cantidad_disponible <= inventory.stock_minimo

        return Response(
            {
                "mensaje": "Stock actualizado correctamente",
                "inventory": InventorySerializer(inventory).data,
                "log": InventoryLogSerializer(log).data,
                "alerta_reabastecimiento": alerta,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="kardex")
    def kardex(self, request):
        product_id = request.query_params.get("product_id")
        branch_id = request.query_params.get("branch_id")

        logs = InventoryLog.objects.select_related("inventory", "usuario").all()

        if product_id:
            logs = logs.filter(inventory__product_id=product_id)
        if branch_id:
            logs = logs.filter(inventory__branch_id=branch_id)

        logs = logs.order_by("-fecha")[:100]
        return Response(InventoryLogSerializer(logs, many=True).data)


# ============================================================
# Cliente
# ============================================================

class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all().order_by("id")
    serializer_class = ClienteSerializer


# ============================================================
# Proveedor
# ============================================================

class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all().order_by("id")
    serializer_class = ProveedorSerializer


# ============================================================
# Factura (with detalles)
# ============================================================

class FacturaViewSet(viewsets.ModelViewSet):
    queryset = Factura.objects.select_related("cliente").prefetch_related("detalles__producto").all()
    serializer_class = FacturaSerializer


# ============================================================
# Pedido (with detalles)
# ============================================================

class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.select_related("cliente").prefetch_related("detalles__producto").all()
    serializer_class = PedidoSerializer


# ============================================================
# Notificacion
# ============================================================

class NotificacionViewSet(viewsets.ModelViewSet):
    queryset = Notificacion.objects.all().order_by("-fecha_creacion")
    serializer_class = NotificacionSerializer


# ============================================================
# Dashboard (dynamic stats from new models)
# ============================================================

class DashboardViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["get"])
    def estadisticas(self, request):
        total_productos = Product.objects.count()
        total_clientes = Cliente.objects.count()
        total_facturas = Factura.objects.count()
        total_pedidos = Pedido.objects.count()

        inventario = Inventory.objects.all()
        unidades_totales = inventario.aggregate(total=Sum("cantidad_disponible"))["total"] or 0
        valor_inventario = 0
        productos_bajo_stock = []

        for inv in inventario.select_related("product"):
            valor_inventario += float(inv.product.precio_compra or 0) * inv.cantidad_disponible
            if inv.cantidad_disponible <= inv.stock_minimo:
                productos_bajo_stock.append({
                    "inventory_id": inv.id,
                    "producto": inv.product.nombre,
                    "sucursal": inv.branch.nombre if inv.branch else None,
                    "cantidad_disponible": inv.cantidad_disponible,
                    "stock_minimo": inv.stock_minimo,
                })

        ventas_por_producto = (
            FacturaDetalle.objects
            .values("producto__id", "producto__nombre")
            .annotate(total_vendido=Sum("cantidad"), total_facturado=Sum("subtotal"))
            .order_by("-total_vendido")[:10]
        )
        ventas_lista = [
            {
                "producto_id": v["producto__id"],
                "nombre_producto": v["producto__nombre"],
                "total_vendido": v["total_vendido"],
                "total_facturado": float(v["total_facturado"] or 0),
            }
            for v in ventas_por_producto
        ]

        movimientos_recientes = InventoryLog.objects.select_related(
            "inventory__product", "inventory__branch", "usuario"
        ).order_by("-fecha")[:10]

        movimientos_data = [
            {
                "id": m.id,
                "producto": m.inventory.product.nombre if m.inventory and m.inventory.product else None,
                "sucursal": m.inventory.branch.nombre if m.inventory and m.inventory.branch else None,
                "tipo_movimiento": m.tipo_movimiento,
                "cantidad": m.cantidad,
                "fecha": m.fecha,
            }
            for m in movimientos_recientes
        ]

        entradas = InventoryLog.objects.filter(tipo_movimiento=InventoryLog.ENTRADA).count()
        salidas = InventoryLog.objects.filter(tipo_movimiento=InventoryLog.SALIDA).count()

        return Response({
            "totales": {
                "productos": total_productos,
                "clientes": total_clientes,
                "facturas": total_facturas,
                "pedidos": total_pedidos,
            },
            "inventario": {
                "unidades_totales": unidades_totales,
                "valor_inventario": round(valor_inventario, 2),
                "productos_bajo_stock": len(productos_bajo_stock),
            },
            "movimientos": {"entradas": entradas, "salidas": salidas},
            "ventas_por_producto": ventas_lista,
            "movimientos_recientes": movimientos_data,
            "reposicion_sugerida": productos_bajo_stock,
        })


# ============================================================
# Asistente IA
# ============================================================

class AsistenteIAView(APIView):
    def post(self, request):
        mensaje = request.data.get("mensaje", "")
        if not mensaje:
            return Response(
                {"detail": "El campo mensaje es obligatorio"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        respuesta = consultar_asistente_effiadmi(mensaje)
        return Response({"mensaje": mensaje, "respuesta": respuesta})
