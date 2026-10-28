"""Cobertura de los comandos de gestion de EFFIADMI."""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .management.commands.revisar_claves_debiles import CLAVES_DEBILES, clave_aleatoria
from .management.commands.setup_inicial import password_aleatoria
from .models import Branch, UserProfile


class ExportarRespaldoTest(TestCase):
    def test_exporta_json_en_utf8(self):
        User.objects.create_user(username="respaldo@test.com", password="ClaveSegura123!")

        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "respaldo.json"
            salida = StringIO()
            call_command("exportar_respaldo", str(ruta), stdout=salida)

            self.assertTrue(ruta.exists())
            contenido = ruta.read_text(encoding="utf-8")
            self.assertIsInstance(json.loads(contenido), list)
            self.assertIn("Respaldo exportado en UTF-8", salida.getvalue())

    def test_error_al_escribir_el_respaldo(self):
        with tempfile.TemporaryDirectory() as directorio:
            with self.assertRaises(CommandError):
                call_command(
                    "exportar_respaldo", directorio, stdout=StringIO(), stderr=StringIO()
                )


class RestaurarRespaldoTest(TestCase):
    @patch("effiadmi.management.commands.restaurar_respaldo.connection")
    @patch("effiadmi.management.commands.restaurar_respaldo.call_command")
    def test_carga_respaldo_y_reinicia_secuencias(self, mock_call, mock_connection):
        mock_call.side_effect = ["", "SELECT 1;\nSELECT 2;"]
        cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = cursor
        salida = StringIO()

        call_command("restaurar_respaldo", "respaldo.json", stdout=salida)

        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn("Secuencias reiniciadas correctamente: 2", salida.getvalue())

    @patch("effiadmi.management.commands.restaurar_respaldo.connection")
    @patch("effiadmi.management.commands.restaurar_respaldo.call_command")
    def test_sin_secuencias_por_reiniciar(self, mock_call, mock_connection):
        mock_call.side_effect = ["", ""]
        salida = StringIO()

        call_command("restaurar_respaldo", "respaldo.json", stdout=salida)

        self.assertIn("No hay secuencias que reiniciar", salida.getvalue())
        mock_connection.cursor.assert_not_called()


class RevisarClavesDebilesTest(TestCase):
    def setUp(self):
        self.debil = User.objects.create_user(
            username="debil@test.com", password="admin123"
        )
        self.fuerte = User.objects.create_user(
            username="fuerte@test.com", password="ClaveSegura123!"
        )

    def test_sin_claves_debiles(self):
        self.debil.set_password("ClaveSegura123!")
        self.debil.save(update_fields=["password"])
        salida = StringIO()

        call_command("revisar_claves_debiles", stdout=salida)

        self.assertIn("No se encontraron contrasenas debiles", salida.getvalue())

    def test_lista_sin_aplicar_cambios(self):
        salida = StringIO()

        call_command("revisar_claves_debiles", stdout=salida)

        self.assertIn("DEBIL: 'debil@test.com'", salida.getvalue())
        self.assertIn("Cuentas a rotar: 1", salida.getvalue())
        self.debil.refresh_from_db()
        self.assertTrue(self.debil.check_password("admin123"))

    @patch(
        "effiadmi.management.commands.revisar_claves_debiles.clave_aleatoria",
        return_value="NuevaClave123!",
    )
    def test_aplica_rotacion_de_claves(self, _clave):
        salida = StringIO()

        call_command("revisar_claves_debiles", "--aplicar", stdout=salida)

        self.debil.refresh_from_db()
        self.fuerte.refresh_from_db()
        self.assertTrue(self.debil.check_password("NuevaClave123!"))
        self.assertTrue(self.fuerte.check_password("ClaveSegura123!"))
        self.assertIn("Nueva contrasena: NuevaClave123!", salida.getvalue())
        self.assertIn("Cuentas afectadas: 1", salida.getvalue())


class GeneradoresDeClavesTest(TestCase):
    def test_clave_aleatoria_tiene_longitud_y_caracteres_validos(self):
        clave = clave_aleatoria()
        self.assertEqual(len(clave), 18)
        permitidos = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%*-_"
        )
        self.assertTrue(set(clave) <= permitidos)
        self.assertNotIn(clave, CLAVES_DEBILES)

    def test_password_inicial_es_alfanumerica(self):
        clave = password_aleatoria()
        self.assertEqual(len(clave), 18)
        self.assertTrue(clave.isalnum())


class SetupInicialTest(TestCase):
    @patch(
        "effiadmi.management.commands.setup_inicial.password_aleatoria",
        return_value="ClaveInicial123",
    )
    def test_crea_usuario_perfil_y_sucursal(self, _password):
        salida = StringIO()

        call_command("setup_inicial", stdout=salida)

        usuario = User.objects.get(username="admin@example.com")
        self.assertTrue(usuario.check_password("ClaveInicial123"))
        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.is_superuser)
        self.assertEqual(UserProfile.objects.get(user=usuario).cargo, "admin")
        self.assertTrue(Branch.objects.filter(nombre="Sucursal Principal").exists())
        self.assertIn("Datos iniciales listos", salida.getvalue())

    def test_omite_usuario_existente_con_clave_fuerte(self):
        usuario = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="ClaveSegura123!",
        )
        salida = StringIO()

        call_command("setup_inicial", stdout=salida)

        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("ClaveSegura123!"))
        self.assertIn("ya existe, omitiendo", salida.getvalue())

    @patch(
        "effiadmi.management.commands.setup_inicial.password_aleatoria",
        return_value="ClaveRotada123",
    )
    def test_rota_clave_por_defecto(self, _password):
        usuario = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="admin123",
        )
        salida = StringIO()

        call_command("setup_inicial", stdout=salida)

        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("ClaveRotada123"))
        self.assertIn("fue rotada", salida.getvalue())
