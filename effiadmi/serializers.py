from rest_framework import serializers

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


class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = productos
        fields = '__all__'


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = proveedores
        fields = '__all__'


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clientes
        fields = '__all__'


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'nombre_usuario', 'apellido_usuario', 'email', 'cargo', 'fecha_registro']
        read_only_fields = ['fecha_registro']


class FacturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = facturas
        fields = '__all__'


class PedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = pedidos
        fields = '__all__'


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = notificaciones
        fields = '__all__'


class InventarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventario
        fields = '__all__'


class MovimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = movimientos
        fields = ['id', 'producto', 'tipo', 'cantidad', 'descripcion', 'fecha', 'usuario']
        read_only_fields = ['fecha']


# ============================================================
# Serializers: Branch, Product, Inventory, InventoryLog
# ============================================================

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
        choices=InventoryLog.TIPO_MOVIMIENTO_CHOICES
    )
    cantidad = serializers.IntegerField(min_value=1)
    motivo = serializers.CharField(required=False, default="")
