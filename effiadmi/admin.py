from django.contrib import admin
from .models import *

# Register your models here.
@admin.register(Clientes)
class ClientesAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'telefono', 'direccion')
<<<<<<< HEAD
=======

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

>>>>>>> b9abaf4 (Carpeta api creada y descarga de librerias)
