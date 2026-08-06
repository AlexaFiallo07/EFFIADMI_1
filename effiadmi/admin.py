from django.contrib import admin
from .models import *

# Register your models here.
@admin.register(Clientes)
class ClientesAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'telefono', 'direccion')
