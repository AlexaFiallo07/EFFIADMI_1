from django.contrib import admin
from .models import *

# Register your models here.
@admin.register(Clientes)
class ClientesAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'telefono', 'direccion')

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('nombre_usuario', 'apellido_usuario', 'email', 'cargo', 'fecha_registro')
    list_filter = ('cargo', 'fecha_registro')
    search_fields = ('nombre_usuario', 'apellido_usuario', 'email')
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre_usuario', 'apellido_usuario', 'email')
        }),
        ('Seguridad', {
            'fields': ('contraseña',)
        }),
        ('Cargo', {
            'fields': ('cargo',)
        }),
        ('Registro', {
            'fields': ('fecha_registro',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('fecha_registro',)

@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = ('nombre_producto', 'stock_actual', 'stock_minimo', 'precio_venta', 'fecha_creacion')
    list_filter = ('fecha_creacion',)
    search_fields = ('nombre_producto',)

@admin.register(facturas)
class FacturasAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'fecha_emision', 'total')
    list_filter = ('fecha_emision',)
    search_fields = ('cliente__nombre',)

@admin.register(notificaciones)
class NotificacionesAdmin(admin.ModelAdmin):
    list_display = ('id', 'mensaje', 'fecha_creacion', 'leido')
    list_filter = ('leido', 'fecha_creacion')
    search_fields = ('mensaje',)

@admin.register(pedidos)
class PedidosAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'fecha_pedido', 'total')
    list_filter = ('fecha_pedido',)
    search_fields = ('cliente__nombre',)

@admin.register(productos)
class ProductosAdmin(admin.ModelAdmin):
    list_display = ('nombre_producto', 'precio_venta', 'precio_compra', 'stock_actual')
    list_filter = ('stock_actual',)
    search_fields = ('nombre_producto',)

@admin.register(proveedores)
class ProveedoresAdmin(admin.ModelAdmin):
    list_display = ('nombre_proveedor', 'correo', 'telefono', 'direccion')
    search_fields = ('nombre_proveedor', 'correo')



