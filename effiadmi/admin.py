from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import (
    UserProfile, Branch, Product, Inventory, InventoryLog,
    Cliente, Proveedor, ProveedorProducto,
    Factura, FacturaDetalle, Pedido, PedidoDetalle,
    Notificacion, ChatHistorial,
)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False


class CustomUserAdmin(UserAdmin):
    inlines = [UserProfileInline]
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion', 'es_principal')
    list_filter = ('es_principal',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'nombre', 'categoria', 'precio_venta')
    list_filter = ('categoria',)
    search_fields = ('sku', 'nombre')


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'branch', 'cantidad_disponible', 'stock_minimo')
    list_filter = ('branch',)


@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    list_display = ('inventory', 'tipo_movimiento', 'cantidad', 'cantidad_resultante', 'usuario', 'fecha')
    list_filter = ('tipo_movimiento', 'fecha')
    search_fields = ('motivo',)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'telefono')
    search_fields = ('nombre', 'correo')


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'telefono')
    search_fields = ('nombre', 'correo')


@admin.register(ProveedorProducto)
class ProveedorProductoAdmin(admin.ModelAdmin):
    list_display = ('proveedor', 'producto', 'precio_compra')
    list_filter = ('proveedor',)


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'usuario', 'total', 'fecha_emision')
    list_filter = ('fecha_emision',)
    search_fields = ('cliente__nombre',)


@admin.register(FacturaDetalle)
class FacturaDetalleAdmin(admin.ModelAdmin):
    list_display = ('factura', 'producto', 'cantidad', 'precio_unitario', 'subtotal')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'usuario', 'estado', 'total', 'fecha_pedido')
    list_filter = ('estado', 'fecha_pedido')
    search_fields = ('cliente__nombre',)


@admin.register(PedidoDetalle)
class PedidoDetalleAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'producto', 'cantidad', 'precio_unitario', 'subtotal')


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'mensaje', 'leido', 'fecha_creacion')
    list_filter = ('leido', 'fecha_creacion')


@admin.register(ChatHistorial)
class ChatHistorialAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha')
    list_filter = ('fecha',)
