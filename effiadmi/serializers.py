from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (
    Branch,
    Cliente,
    ChatHistorial,
    Factura,
    FacturaDetalle,
    Inventory,
    InventoryLog,
    Notificacion,
    Pedido,
    PedidoDetalle,
    Product,
    Proveedor,
    ProveedorProducto,
    UserProfile,
)


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id", "user", "username", "email", "first_name", "last_name",
            "telefono", "direccion", "cargo",
        ]
        read_only_fields = ["user"]


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):
    sucursal_id = serializers.IntegerField(required=False, write_only=True)
    stock_inicial = serializers.IntegerField(required=False, write_only=True, default=0)
    stock_minimo_inicial = serializers.IntegerField(required=False, write_only=True, default=5)

    class Meta:
        model = Product
        fields = [
            "id", "sku", "nombre", "descripcion", "categoria", "precio_venta",
            "sucursal_id", "stock_inicial", "stock_minimo_inicial",
        ]

    def create(self, validated_data):
        from django.db import transaction

        sucursal_id = validated_data.pop("sucursal_id", None)
        stock_inicial = validated_data.pop("stock_inicial", 0)
        stock_minimo_inicial = validated_data.pop("stock_minimo_inicial", 5)

        with transaction.atomic():
            product = Product.objects.create(**validated_data)

            branch = Branch.objects.filter(es_principal=True).first()
            if sucursal_id:
                branch = Branch.objects.filter(id=sucursal_id).first()
                if not branch:
                    raise serializers.ValidationError(
                        {"sucursal_id": "La sucursal indicada no existe."}
                    )
            if not branch:
                branch = Branch.objects.create(
                    nombre="Sucursal Principal",
                    direccion="",
                    es_principal=True,
                )

            inventory = Inventory.objects.create(
                product=product,
                branch=branch,
                cantidad_disponible=stock_inicial,
                stock_minimo=stock_minimo_inicial,
            )

            if stock_inicial > 0:
                InventoryLog.objects.create(
                    inventory=inventory,
                    tipo_movimiento=InventoryLog.ENTRADA,
                    cantidad=stock_inicial,
                    cantidad_resultante=stock_inicial,
                    motivo="Creación automática de producto con stock inicial",
                )

        return product


class InventorySerializer(serializers.ModelSerializer):
    product_nombre = serializers.CharField(source="product.nombre", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    branch_nombre = serializers.CharField(source="branch.nombre", read_only=True)

    class Meta:
        model = Inventory
        fields = [
            "id", "product", "branch", "cantidad_disponible", "stock_minimo",
            "product_nombre", "product_sku", "branch_nombre",
        ]


class InventoryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLog
        fields = [
            "id", "inventory", "tipo_movimiento", "cantidad",
            "cantidad_resultante", "motivo", "usuario", "fecha",
        ]
        read_only_fields = ["fecha", "cantidad_resultante"]


class StockAdjustSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    sucursal_id = serializers.IntegerField()
    tipo_movimiento = serializers.ChoiceField(
        choices=InventoryLog.TIPO_MOVIMIENTO_CHOICES,
    )
    cantidad = serializers.IntegerField(min_value=1)
    motivo = serializers.CharField(required=False, default="")


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = "__all__"


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = "__all__"


class ProveedorProductoSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source="proveedor.nombre", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = ProveedorProducto
        fields = [
            "id", "proveedor", "producto", "precio_compra",
            "proveedor_nombre", "producto_nombre",
        ]


class FacturaDetalleSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = FacturaDetalle
        fields = [
            "id", "producto", "producto_nombre", "cantidad",
            "precio_unitario", "subtotal",
        ]
        read_only_fields = ["subtotal"]


class FacturaSerializer(serializers.ModelSerializer):
    detalles = FacturaDetalleSerializer(many=True, read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True, default="")

    class Meta:
        model = Factura
        fields = [
            "id", "cliente", "cliente_nombre", "usuario", "usuario_username",
            "fecha_emision", "total", "detalles",
        ]
        read_only_fields = ["fecha_emision", "total"]


class PedidoDetalleSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = PedidoDetalle
        fields = [
            "id", "producto", "producto_nombre", "cantidad",
            "precio_unitario", "subtotal",
        ]
        read_only_fields = ["subtotal"]


class PedidoSerializer(serializers.ModelSerializer):
    detalles = PedidoDetalleSerializer(many=True, read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True, default="")

    class Meta:
        model = Pedido
        fields = [
            "id", "cliente", "cliente_nombre", "usuario", "usuario_username",
            "fecha_pedido", "estado", "total", "detalles",
        ]
        read_only_fields = ["fecha_pedido", "total"]


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = "__all__"
        read_only_fields = ["fecha_creacion"]


class ChatHistorialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatHistorial
        fields = "__all__"
        read_only_fields = ["fecha"]
