"""Pruebas de seguridad: CSRF, cabeceras, /media/ protegido, login y recuperacion."""

import os
import shutil
import tempfile

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .soporte_pruebas import EffiBaseTestCase, textos_mensajes


class CsrfTest(TestCase):
    def test_post_sin_token_csrf_da_403(self):
        cliente = Client(enforce_csrf_checks=True)
        respuesta = cliente.post(reverse("effiadmi:crear_cliente"), {"nombre": "x"})
        self.assertEqual(respuesta.status_code, 403)


class CabecerasSeguridadTest(TestCase):
    def test_cabeceras_presentes(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta["X-Frame-Options"], "DENY")
        self.assertEqual(respuesta["X-Content-Type-Options"], "nosniff")
        self.assertEqual(respuesta["Referrer-Policy"], "same-origin")


class MediaProtegidaTest(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        with open(os.path.join(self.media, "factura.txt"), "w", encoding="utf-8") as archivo:
            archivo.write("contenido privado")

    def test_anonimo_recibe_404(self):
        with override_settings(MEDIA_ROOT=self.media):
            respuesta = self.client.get("/media/factura.txt")
        self.assertEqual(respuesta.status_code, 404)

    def test_con_sesion_recibe_el_archivo(self):
        session = self.client.session
        session["logueado"] = {"id": 1, "nombre": "X", "rol": "admin"}
        session.save()
        with override_settings(MEDIA_ROOT=self.media):
            respuesta = self.client.get("/media/factura.txt")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(b"".join(respuesta.streaming_content), b"contenido privado")

    def test_archivo_inexistente_da_404(self):
        session = self.client.session
        session["logueado"] = {"id": 1, "nombre": "X", "rol": "admin"}
        session.save()
        with override_settings(MEDIA_ROOT=self.media):
            respuesta = self.client.get("/media/no-existe.txt")
        self.assertEqual(respuesta.status_code, 404)


class LoginCandadoTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("effiadmi:login")

    def test_login_valido_crea_sesion(self):
        respuesta = self.client.post(
            self.url, {"username": self.operador.email, "password": "ClaveSegura123!"}, follow=True
        )
        self.assertEqual(self.client.session.get("logueado", {}).get("rol"), "operador")
        self.assertIn("Bienvenido", " ".join(textos_mensajes(respuesta)))

    def test_bloquea_tras_cinco_fallos(self):
        for _ in range(5):
            self.client.post(self.url, {"username": self.operador.email, "password": "mala"})
        respuesta = self.client.post(
            self.url, {"username": self.operador.email, "password": "ClaveSegura123!"}, follow=True
        )
        self.assertNotIn("logueado", self.client.session)
        self.assertIn("Demasiados intentos fallidos", " ".join(textos_mensajes(respuesta)))

    def test_login_valido_limpia_los_fallos(self):
        for _ in range(3):
            self.client.post(self.url, {"username": self.operador.email, "password": "mala"})
        self.client.post(self.url, {"username": self.operador.email, "password": "ClaveSegura123!"})
        self.assertIsNone(cache.get(f"login_fallos:{self.operador.email}"))


class LoginThrottleMiddlewareTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_limita_los_post_por_ip(self):
        url = reverse("effiadmi:login")
        ultimo = None
        for i in range(11):
            ultimo = self.client.post(url, {"username": f"u{i}@test.com", "password": "x"})
        self.assertEqual(ultimo.status_code, 429)
        self.assertIn("Demasiados intentos", ultimo.content.decode())


class RecuperacionTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.url_solicitar = reverse("effiadmi:solicitar_recuperacion")

    def test_email_desconocido_no_revela_si_existe(self):
        respuesta = self.client.post(self.url_solicitar, {"email": "nadie@test.com"})
        self.assertTrue(respuesta.context["enviado"])

    def test_email_invalido_muestra_error(self):
        respuesta = self.client.post(self.url_solicitar, {"email": "no-es-un-correo"})
        self.assertIn("error", respuesta.context)

    def test_token_valido_permite_abrir_el_formulario(self):
        from .views import token_recuperacion

        token = token_recuperacion(self.operador)
        respuesta = self.client.get(reverse("effiadmi:restablecer_password", args=[token]))
        self.assertTrue(respuesta.context["valido"])

    def test_token_manipulado_es_invalido(self):
        from .views import token_recuperacion

        token = token_recuperacion(self.operador)
        respuesta = self.client.get(
            reverse("effiadmi:restablecer_password", args=[token[:-2] + "xx"])
        )
        self.assertFalse(respuesta.context["valido"])

    def test_token_deja_de_servir_al_cambiar_la_contrasena(self):
        from .views import token_recuperacion, usuario_desde_token

        token = token_recuperacion(self.operador)
        self.operador.set_password("OtraClaveDistinta2026!")
        self.operador.save()
        self.assertIsNone(usuario_desde_token(token))

    def test_restablecer_cambia_la_contrasena(self):
        from .views import token_recuperacion

        token = token_recuperacion(self.operador)
        self.client.post(
            reverse("effiadmi:restablecer_password", args=[token]),
            {"password": "NuevaClaveSegura2026!", "password_confirm": "NuevaClaveSegura2026!"},
            follow=True,
        )
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.check_password("NuevaClaveSegura2026!"))

    def test_contrasenas_distintas_no_cambian_nada(self):
        from .views import token_recuperacion

        token = token_recuperacion(self.operador)
        respuesta = self.client.post(
            reverse("effiadmi:restablecer_password", args=[token]),
            {"password": "NuevaClaveSegura2026!", "password_confirm": "OtraClave123!"},
        )
        self.assertTrue(respuesta.context["valido"])
        self.assertIn("error", respuesta.context)
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.check_password("ClaveSegura123!"))
