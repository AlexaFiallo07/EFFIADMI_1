from django.db import transaction
from django.db.models import Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from .models import (
    Branch,
    Clientes,
    Inventario,
    Inventory,
    InventoryLog,
    Product,
    Usuario,
    facturas,
    notificaciones,
    pedidos,
    productos,
    proveedores,
    movimientos,
)
from .serializers import (
    BranchSerializer,
    ClienteSerializer,
    FacturaSerializer,
    InventarioSerializer,
    InventoryLogSerializer,
    InventorySerializer,
    MovimientoSerializer,
    NotificacionSerializer,
    PedidoSerializer,
    ProductoSerializer,
    ProductSerializer,
    ProveedorSerializer,
    StockAdjustSerializer,
    UsuarioSerializer,
)
from .servicio_ia import consultar_asistente_effiadmi


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = productos.objects.all().order_by('id')
    serializer_class = ProductoSerializer


class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = proveedores.objects.all().order_by('id')
    serializer_class = ProveedorSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Clientes.objects.all().order_by('id')
    serializer_class = ClienteSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('id')
    serializer_class = UsuarioSerializer


class FacturaViewSet(viewsets.ModelViewSet):
    queryset = facturas.objects.all().order_by('id')
    serializer_class = FacturaSerializer


class PedidoViewSet(viewsets.ModelViewSet):
    queryset = pedidos.objects.all().order_by('id')
    serializer_class = PedidoSerializer


class NotificacionViewSet(viewsets.ModelViewSet):
    queryset = notificaciones.objects.all().order_by('id')
    serializer_class = NotificacionSerializer


class InventarioViewSet(viewsets.ModelViewSet):
    queryset = Inventario.objects.all().order_by('id')
    serializer_class = InventarioSerializer

    @action(detail=False, methods=['get'])
    def bajo_stock(self, request):
        registros = [
            r for r in self.get_queryset()
            if r.stock_actual < r.stock_minimo
        ]
        serializer = self.get_serializer(registros, many=True)
        return Response({
            'data': serializer.data,
            'total': len(serializer.data),
            'mensaje': 'Productos que requieren reposición',
        })

    @action(detail=False, methods=['get'])
    def resumen(self, request):
        total_productos = productos.objects.count()
        unidades_totales = sum(p.stock_actual for p in productos.objects.all())
        valor_inventario = sum(
            float(p.precio_compra) * p.stock_actual for p in productos.objects.all()
        )
        return Response({
            'total_productos': total_productos,
            'unidades_totales': unidades_totales,
            'valor_inventario': valor_inventario,
        })


class MovimientoViewSet(viewsets.ModelViewSet):
    queryset = movimientos.objects.select_related('producto').all()
    serializer_class = MovimientoSerializer

    def perform_create(self, serializer):
        movimiento = serializer.save()
        producto = movimiento.producto
        cantidad = movimiento.cantidad

        if movimiento.tipo == 'entrada':
            producto.stock_actual += cantidad
        elif movimiento.tipo == 'salida':
            if producto.stock_actual < cantidad:
                raise ValidationError(
                    {'detail': f'Stock insuficiente. Stock actual: {producto.stock_actual}'}
                )
            producto.stock_actual -= cantidad
        elif movimiento.tipo == 'ajuste':
            producto.stock_actual = cantidad

        producto.save()

        if producto.stock_actual < producto.stock_minimo:
            notificaciones.objects.create(
                mensaje=(
                    f"El producto '{producto.nombre_producto}' está por debajo del stock "
                    f"mínimo: {producto.stock_actual}/{producto.stock_minimo}"
                )
            )


class DashboardViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        total_productos = productos.objects.count()
        total_proveedores = proveedores.objects.count()
        total_usuarios = Usuario.objects.count()

        unidades_totales = 0
        valor_inventario = 0
        productos_bajos = []
        for producto in productos.objects.all():
            unidades_totales += producto.stock_actual
            valor_inventario += float(producto.precio_compra) * producto.stock_actual
            if producto.stock_actual < producto.stock_minimo:
                productos_bajos.append({
                    'id': producto.id,
                    'nombre_producto': producto.nombre_producto,
                    'stock_actual': producto.stock_actual,
                    'stock_minimo': producto.stock_minimo,
                })

        ventas_por_producto = (
            movimientos.objects
            .filter(tipo='salida')
            .values('producto')
            .annotate(total=Sum('cantidad'))
            .order_by('-total')
        )

        producto_mas_vendido = None
        if ventas_por_producto:
            mejor = ventas_por_producto.first()
            producto_obj = productos.objects.filter(id=mejor['producto']).first()
            producto_mas_vendido = {
                'producto_id': mejor['producto'],
                'nombre_producto': producto_obj.nombre_producto if producto_obj else 'Sin nombre',
                'unidades_vendidas': mejor['total'],
            }

        entradas = movimientos.objects.filter(tipo='entrada').count()
        salidas = movimientos.objects.filter(tipo='salida').count()

        return Response({
            'totales': {
                'productos': total_productos,
                'proveedores': total_proveedores,
                'usuarios': total_usuarios,
            },
            'inventario': {
                'unidades_totales': unidades_totales,
                'valor_inventario': valor_inventario,
                'productos_bajo_stock': len(productos_bajos),
            },
            'movimientos': {'entradas': entradas, 'salidas': salidas},
            'producto_mas_vendido': producto_mas_vendido,
            'reposicion_sugerida': productos_bajos,
        })


class AsistenteIAView(APIView):
    def post(self, request):
        mensaje = request.data.get('mensaje', '')
        if not mensaje:
            return Response(
                {'detail': 'El campo mensaje es obligatorio'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        respuesta = consultar_asistente_effiadmi(mensaje)
        return Response({'mensaje': mensaje, 'respuesta': respuesta})


# ============================================================
# Nuevos ViewSets: Branch, Product, Inventory
# ============================================================

class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all().order_by("id")
    serializer_class = BranchSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("id")
    serializer_class = ProductSerializer


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
