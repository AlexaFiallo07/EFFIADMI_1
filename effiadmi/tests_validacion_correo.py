"""Validacion de correos en login y formularios (usuario, cliente y proveedor)."""

import socket
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Cliente, Proveedor, UserProfile
from .soporte_pruebas import EffiBaseTestCase, textos_mensajes
from .utilidades import validar_correo_electronico


class ValidarCorreoTest(TestCase):
    def test_acepta_correo_con_dominio_y_extension(self):
        self.assertEqual(validar_correo_electronico("juan@gmail.com"), (True, ""))
        self.assertEqual(validar_correo_electronico("juan@empresa.co"), (True, ""))

    def test_rechaza_correo_sin_arroba(self):
        valido, error = validar_correo_electronico("juangmail.com")
        self.assertFalse(valido)
        self.assertIn("símbolo '@'", error)

    def test_rechaza_correo_sin_dominio(self):
        valido, error = validar_correo_electronico("juan@")
        self.assertFalse(valido)
        self.assertIn("incompleto", error)

    def test_rechaza_correo_sin_extension(self):
        valido, error = validar_correo_electronico("juan@gmail")
        self.assertFalse(valido)
        self.assertIn("extensión", error)

    def test_rechaza_extension_invalida_sin_dns(self):
        valido, error = validar_correo_electronico("juan@gmail.con")
        self.assertFalse(valido)
        self.assertIn("extensión del correo no es válida", error)

    def test_rechaza_espacios_y_arrobas_repetidas(self):
        self.assertFalse(validar_correo_electronico("juan @gmail.com")[0])
        self.assertFalse(validar_correo_electronico("juan@@gmail.com")[0])
        self.assertFalse(validar_correo_electronico("juan@gmail..com")[0])


@override_settings(VALIDAR_DOMINIO_CORREO=True)
class DominioCorreoDnsTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch("socket.getaddrinfo", side_effect=socket.gaierror(11001, "no existe"))
    def test_rechaza_dominio_inexistente(self, _mock):
        valido, error = validar_correo_electronico("juan@dominioinexistente12345.com")
        self.assertFalse(valido)
        self.assertIn("dominio del correo no existe", error)

    @patch("socket.getaddrinfo", return_value=[("ok",)])
    def test_acepta_extension_nueva_si_el_dominio_existe(self, _mock):
        self.assertEqual(validar_correo_electronico("juan@dominio.zz"), (True, ""))

    @patch("socket.getaddrinfo", side_effect=socket.gaierror(11001, "no existe"))
    def test_rechaza_extension_nueva_si_el_dominio_no_existe(self, _mock):
        valido, error = validar_correo_electronico("juan@dominio.zz")
        self.assertFalse(valido)
        self.assertIn("no existe", error)

    @patch("socket.getaddrinfo", side_effect=socket.gaierror(-3, "temporal"))
    def test_deja_pasar_si_el_dns_falla_temporalmente(self, _mock):
        self.assertEqual(validar_correo_electronico("juan@gmail.com"), (True, ""))


class FormularioCorreoTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    def test_no_guarda_cliente_con_correo_sin_arroba(self):
        respuesta = self.client.post(
            reverse("effiadmi:crear_cliente"),
            {"nombre": "Juan", "correo": "juangmail.com", "telefono": "3001234567", "direccion": "Calle"},
            follow=True,
        )
        self.assertFalse(Cliente.objects.filter(nombre="Juan").exists())
        self.assertIn("símbolo '@'", " ".join(textos_mensajes(respuesta)))

    def test_no_guarda_cliente_con_extension_invalida(self):
        respuesta = self.client.post(
            reverse("effiadmi:crear_cliente"),
            {"nombre": "Juan", "correo": "juan@gmail.con", "telefono": "3001234567", "direccion": "Calle"},
            follow=True,
        )
        self.assertFalse(Cliente.objects.filter(nombre="Juan").exists())
        self.assertIn("extensión", " ".join(textos_mensajes(respuesta)))

    def test_guarda_cliente_con_correo_valido(self):
        self.client.post(
            reverse("effiadmi:crear_cliente"),
            {"nombre": "Juan", "correo": "juan@test.com", "telefono": "3001234567", "direccion": "Calle"},
            follow=True,
        )
        self.assertTrue(Cliente.objects.filter(correo="juan@test.com").exists())

    def test_no_guarda_proveedor_con_correo_invalido(self):
        respuesta = self.client.post(
            reverse("effiadmi:crear_proveedor"),
            {"nombre_proveedor": "Prov", "correo": "provgmail.com", "telefono": "3001234567", "direccion": "Calle"},
            follow=True,
        )
        self.assertFalse(Proveedor.objects.filter(nombre="Prov").exists())
        self.assertIn("símbolo '@'", " ".join(textos_mensajes(respuesta)))

    def test_no_crea_usuario_con_correo_invalido(self):
        respuesta = self.client.post(
            reverse("effiadmi:crear_usuario"),
            {
                "nombre_usuario": "Nuevo",
                "apellido_usuario": "Oper",
                "email": "nuevo@test",
                "contraseña": "ClaveRobusta2026!",
                "cargo": "operador",
            },
            follow=True,
        )
        self.assertFalse(User.objects.filter(first_name="Nuevo").exists())
        self.assertIn("extensión", " ".join(textos_mensajes(respuesta)))


class LoginSoloCorreoTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.juan = User.objects.create_user(
            username="juan", email="juan@test.com", password=self.CLAVE
        )
        UserProfile.objects.create(user=self.juan, cargo="operador")
        self.url = reverse("effiadmi:login")

    def test_entra_con_correo(self):
        self.client.post(self.url, {"username": "juan@test.com", "password": self.CLAVE})
        self.assertEqual(self.client.session.get("logueado", {}).get("id"), self.juan.id)

    def test_rechaza_usuario_sin_arroba(self):
        respuesta = self.client.post(
            self.url, {"username": "juan", "password": self.CLAVE}, follow=True
        )
        self.assertNotIn("logueado", self.client.session)
        self.assertIn("símbolo '@'", " ".join(textos_mensajes(respuesta)))

    def test_rechaza_correo_sin_arroba(self):
        respuesta = self.client.post(
            self.url, {"username": "juan.gmail.com", "password": self.CLAVE}, follow=True
        )
        self.assertNotIn("logueado", self.client.session)
        self.assertIn("símbolo '@'", " ".join(textos_mensajes(respuesta)))

    def test_rechaza_correo_sin_extension(self):
        respuesta = self.client.post(
            self.url, {"username": "juan@gmail", "password": self.CLAVE}, follow=True
        )
        self.assertNotIn("logueado", self.client.session)
        self.assertIn("extensión", " ".join(textos_mensajes(respuesta)))

    def test_rechaza_extension_invalida(self):
        respuesta = self.client.post(
            self.url, {"username": "juan@gmail.con", "password": self.CLAVE}, follow=True
        )
        self.assertNotIn("logueado", self.client.session)
        self.assertIn("extensión", " ".join(textos_mensajes(respuesta)))
