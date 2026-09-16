from django.db import models


class MensajeContacto(models.Model):
    nombre = models.CharField("Nombre", max_length=120)
    correo = models.EmailField("Correo electrónico")
    asunto = models.CharField("Asunto", max_length=200, blank=True)
    mensaje = models.TextField("Mensaje")
    creado = models.DateTimeField("Recibido", auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje de contacto"
        verbose_name_plural = "Mensajes de contacto"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} ({self.correo})"
