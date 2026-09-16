from django.test import TestCase
from django.urls import reverse

from .models import MensajeContacto


class LandingViewTest(TestCase):
    def test_carga_landing(self):
        respuesta = self.client.get(reverse("landing"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "EFFIADMI")
        self.assertContains(respuesta, "Acceder al sistema")

    def test_pasa_url_sistema(self):
        respuesta = self.client.get(reverse("landing"))
        self.assertContains(respuesta, "/login/")

    def test_formulario_valido(self):
        respuesta = self.client.post(
            reverse("landing"),
            {"nombre": "Juan", "correo": "juan@test.com", "asunto": "Demo", "mensaje": "Hola"},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        mensajes = [m for m in respuesta.context["messages"]]
        self.assertTrue(any("Gracias por escribirnos" in m.message for m in mensajes))

    def test_formulario_requiere_correo_valido(self):
        respuesta = self.client.post(
            reverse("landing"),
            {"nombre": "Juan", "correo": "correo-invalido", "asunto": "Demo", "mensaje": "Hola"},
            follow=True,
        )
        mensajes = [m for m in respuesta.context["messages"]]
        self.assertTrue(any("correo" in m.message for m in mensajes))

    def test_formulario_guarda_en_bd(self):
        self.assertEqual(MensajeContacto.objects.count(), 0)
        self.client.post(
            reverse("landing"),
            {"nombre": "Ana", "correo": "ana@test.com", "asunto": "Demo", "mensaje": "Quiero más info"},
            follow=True,
        )
        self.assertEqual(MensajeContacto.objects.count(), 1)
        registro = MensajeContacto.objects.first()
        self.assertEqual(registro.nombre, "Ana")
        self.assertEqual(registro.correo, "ana@test.com")
        self.assertEqual(registro.asunto, "Demo")

    def test_formulario_invalido_no_guarda(self):
        self.client.post(
            reverse("landing"),
            {"nombre": "", "correo": "x@test.com", "asunto": "", "mensaje": "Hola"},
            follow=True,
        )
        self.assertEqual(MensajeContacto.objects.count(), 0)
