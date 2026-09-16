from django.contrib import admin

from .models import MensajeContacto


@admin.register(MensajeContacto)
class MensajeContactoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "correo", "asunto", "creado")
    list_filter = ("creado",)
    search_fields = ("nombre", "correo", "asunto", "mensaje")
    readonly_fields = ("nombre", "correo", "asunto", "mensaje", "creado")
