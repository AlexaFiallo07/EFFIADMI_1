from rest_framework import serializers

from .models import (
    Clientes,
    Inventario,
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
