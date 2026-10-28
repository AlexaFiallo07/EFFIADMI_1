from decimal import Decimal

from django.db import transaction
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
from .utilidades import cargo_de_usuario


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
        # 'cargo' editable permitiria escalarse a admin a uno mismo.
        read_only_fields = ["user", "cargo"]


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

    def validate_sku(self, value):
        # Product.clean() existe pero DRF no lo llama, asi que por la API se
        # colaba un sku no numerico (el que genera _siguiente_id_producto
        # descarta) y la web lo rechazaba con un error distinto.
        if not str(value).isdigit():
            raise serializers.ValidationError(
                "El ID del producto debe contener solo numeros."
            )
        return value

    def validate_precio_venta(self, value):
        if value is None:
            return value
        if value <= 0:
            raise serializers.ValidationError("El precio de venta debe ser mayor a 0.")
        if value != value.to_integral_value():
            raise serializers.ValidationError(
                "El precio debe ser un valor entero en pesos colombianos, sin decimales."
            )
        if value < 1000 or value > 100000000:
            raise serializers.ValidationError(
                "El precio de venta debe estar entre $1.000 y $100.000.000 (pesos colombianos)."
            )
        return value

    def create(self, validated_data):
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
        # 'cantidad_disponible' solo se cambia por la accion ajustar_stock, que
        # valida que haya stock y deja el InventoryLog correspondiente. Aceptarlo
        # aqui dejaba cambiar el stock sin kardex y sin comprobar existencias.
        read_only_fields = ["cantidad_disponible"]


class InventoryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLog
        fields = [
            "id", "inventory", "tipo_movimiento", "cantidad",
            "cantidad_resultante", "motivo", "usuario", "fecha",
        ]
        read_only_fields = ["fecha", "cantidad_resultante", "usuario"]


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
    cantidad = serializers.IntegerField(min_value=1)
    precio_unitario = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("1000"),
        max_value=Decimal("100000000"),
    )

    class Meta:
        model = FacturaDetalle
        fields = [
            "id", "producto", "producto_nombre", "cantidad",
            "precio_unitario", "subtotal",
        ]
        read_only_fields = ["subtotal"]


class FacturaSerializer(serializers.ModelSerializer):
    # Writable en la creacion: antes era read_only y POST /api/facturas/
    # generaba una factura 'emitida' con total=0 y sin lineas.
    detalles = FacturaDetalleSerializer(many=True, required=False)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True, default="")

    class Meta:
        model = Factura
        fields = [
            "id", "cliente", "cliente_nombre", "usuario", "usuario_username",
            "fecha_emision", "total", "estado", "detalles",
        ]
        # 'usuario' writable dejaba emitir facturas a nombre de otro usuario.
        # 'estado' solo se cambia con la accion de anulacion (web).
        read_only_fields = ["fecha_emision", "total", "usuario", "estado"]

    def validate(self, attrs):
        # required=False evita que DRF exija 'detalles', asi que la exigencia
        # se hace aqui: sin lineas no hay factura que emitir.
        if self.instance is None and not attrs.get("detalles"):
            raise serializers.ValidationError({
                "detalles": "La factura debe incluir al menos una linea en 'detalles'."
            })
        return attrs

    def validate_cliente(self, value):
        if self.instance is not None:
            request = self.context.get("request")
            if cargo_de_usuario(getattr(request, "user", None)) != "admin":
                raise serializers.ValidationError(
                    "Solo un administrador puede reasignar el cliente de una factura."
                )
        return value

    def create(self, validated_data):
        detalles = validated_data.pop("detalles", [])
        with transaction.atomic():
            factura = Factura.objects.create(**validated_data)
            total = 0
            for linea in detalles:
                detalle = FacturaDetalle.objects.create(factura=factura, **linea)
                total += detalle.subtotal
            factura.total = total
            factura.save(update_fields=["total"])
        return factura

    def update(self, instance, validated_data):
        # Una factura emitida no se reescribe: se anula y se crea otra.
        if "detalles" in validated_data:
            raise serializers.ValidationError({
                "detalles": "Las facturas emitidas no se editan. Anula y crea una nueva."
            })
        return super().update(instance, validated_data)


class PedidoDetalleSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    cantidad = serializers.IntegerField(min_value=1)
    precio_unitario = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("1000"),
        max_value=Decimal("100000000"),
    )

    class Meta:
        model = PedidoDetalle
        fields = [
            "id", "producto", "producto_nombre", "cantidad",
            "precio_unitario", "subtotal",
        ]
        read_only_fields = ["subtotal"]


class PedidoSerializer(serializers.ModelSerializer):
    # Writable en la creacion: antes era read_only y POST /api/pedidos/
    # generaba un pedido 'pendiente' con total=0 y sin lineas.
    detalles = PedidoDetalleSerializer(many=True, required=False)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    usuario_username = serializers.CharField(source="usuario.username", read_only=True, default="")

    class Meta:
        model = Pedido
        fields = [
            "id", "cliente", "cliente_nombre", "usuario", "usuario_username",
            "fecha_pedido", "estado", "total", "detalles",
        ]
        # 'estado' editable permitia marcar un pedido como pagado por la API sin
        # pasar por pagar_pedido (que es genera la factura y avisa a los admins).
        read_only_fields = ["fecha_pedido", "total", "usuario", "estado"]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("detalles"):
            raise serializers.ValidationError({
                "detalles": "El pedido debe incluir al menos una linea en 'detalles'."
            })
        return attrs

    def validate_cliente(self, value):
        # Un operador puede editar un pedido, pero no reasignarlo a otro
        # cliente (en la web editar_pedido es solo admin).
        if self.instance is not None:
            request = self.context.get("request")
            if cargo_de_usuario(getattr(request, "user", None)) != "admin":
                raise serializers.ValidationError(
                    "Solo un administrador puede reasignar el cliente de un pedido."
                )
        return value

    def create(self, validated_data):
        detalles = validated_data.pop("detalles", [])
        with transaction.atomic():
            pedido = Pedido.objects.create(**validated_data)
            total = 0
            for linea in detalles:
                detalle = PedidoDetalle.objects.create(pedido=pedido, **linea)
                total += detalle.subtotal
            pedido.total = total
            pedido.save(update_fields=["total"])
        return pedido

    def update(self, instance, validated_data):
        detalles = validated_data.pop("detalles", None)
        with transaction.atomic():
            for campo, valor in validated_data.items():
                setattr(instance, campo, valor)
            instance.save()
            if detalles is not None:
                instance.detalles.all().delete()
                total = 0
                for linea in detalles:
                    detalle = PedidoDetalle.objects.create(pedido=instance, **linea)
                    total += detalle.subtotal
                instance.total = total
                instance.save(update_fields=["total"])
        return instance


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = "__all__"
        # Las notificaciones las genera la aplicacion (utilidades.crear_
        # notificacion); el cliente solo debe poder marcar la suya como leida.
        # 'usuario' editable permitia crear o reasignar notificaciones de
        # cualquier otro usuario, y 'mensaje'/'enlace' dejaaban reescribir el
        # texto de avisos del sistema (stock bajo, pedido confirmado...).
        read_only_fields = ["usuario", "mensaje", "enlace", "fecha_creacion"]


class ChatHistorialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatHistorial
        fields = "__all__"
        read_only_fields = ["fecha"]
