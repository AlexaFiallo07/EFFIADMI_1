from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import MensajeContacto
from .views import MAX_ASUNTO_CONTACTO, MAX_MENSAJE_CONTACTO


class LandingViewTest(TestCase):
    def setUp(self):
        # El antispam por IP vive en la cache (locmem) y esta persiste entre
        # tests; sin limpiarla los POST de un test consumen el cupo del siguiente.
        cache.clear()

    def test_carga_landing(self):
        respuesta = self.client.get(reverse("landing"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "EFFIADMI")
        self.assertContains(respuesta, "Acceder al sistema")

    def test_pasa_url_sistema(self):
        respuesta = self.client.get(reverse("landing"))
        self.assertContains(respuesta, "/login/")

    def test_formulario_valido(self):
        from django.conf import settings as cfg
        from django.core import mail

        respuesta = self.client.post(
            reverse("contacto"),
            {"nombre": "Juan", "correo": "juan@test.com", "asunto": "Demo", "mensaje": "Hola"},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        mensajes = [m for m in respuesta.context["messages"]]
        self.assertTrue(any("Gracias por escribirnos" in m.message for m in mensajes))

        # En la suite el SMTP es locmem, asi que el aviso de contacto debe
        # estar en el outbox dirigido al Gmail del sistema (el mismo SMTP
        # que envia los correos del modulo de Correos).
        if cfg.EMAIL_BACKEND.endswith("locmem.EmailBackend"):
            self.assertTrue(
                any(cfg.EMAIL_HOST_USER in m.to for m in mail.outbox)
            )
            self.assertTrue(
                any("juan@test.com" in m.body for m in mail.outbox)
            )

    def test_formulario_requiere_correo_valido(self):
        respuesta = self.client.post(
            reverse("contacto"),
            {"nombre": "Juan", "correo": "correo-invalido", "asunto": "Demo", "mensaje": "Hola"},
            follow=True,
        )
        mensajes = [m for m in respuesta.context["messages"]]
        self.assertTrue(any("correo" in m.message for m in mensajes))

    def test_formulario_rechaza_asunto_largo(self):
        respuesta = self.client.post(
            reverse("contacto"),
            {
                "nombre": "Juan",
                "correo": "juan@test.com",
                "asunto": "x" * (MAX_ASUNTO_CONTACTO + 1),
                "mensaje": "Hola",
            },
            follow=True,
        )
        mensajes = [m for m in respuesta.context["messages"]]
        self.assertTrue(any("asunto" in m.message for m in mensajes))
        self.assertEqual(MensajeContacto.objects.count(), 0)

    def test_formulario_rechaza_mensaje_largo(self):
        respuesta = self.client.post(
            reverse("contacto"),
            {
                "nombre": "Juan",
                "correo": "juan@test.com",
                "asunto": "Demo",
                "mensaje": "x" * (MAX_MENSAJE_CONTACTO + 1),
            },
            follow=True,
        )
        mensajes = [m for m in respuesta.context["messages"]]
        self.assertTrue(any("mensaje" in m.message for m in mensajes))
        self.assertEqual(MensajeContacto.objects.count(), 0)

    def test_formulario_guarda_en_bd(self):
        self.assertEqual(MensajeContacto.objects.count(), 0)
        self.client.post(
            reverse("contacto"),
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
            reverse("contacto"),
            {"nombre": "", "correo": "x@test.com", "asunto": "", "mensaje": "Hola"},
            follow=True,
        )
        self.assertEqual(MensajeContacto.objects.count(), 0)

    def test_antispam_bloquea_envios_masivos(self):
        datos = {"nombre": "Ana", "correo": "ana@test.com", "asunto": "Demo", "mensaje": "Hola"}
        for _ in range(5):
            self.client.post(reverse("contacto"), datos, follow=True)
        self.assertEqual(MensajeContacto.objects.count(), 5)
        # El sexto POST desde la misma IP queda bloqueado por el limite.
        self.client.post(reverse("contacto"), datos, follow=True)
        self.assertEqual(MensajeContacto.objects.count(), 5)
