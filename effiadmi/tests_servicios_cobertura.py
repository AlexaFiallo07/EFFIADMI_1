"""Cobertura de servicios, utilidades y serializadores."""

import os
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework import serializers

from .models import (
    Branch,
    Categoria,
    Cliente,
    Factura,
    Inventory,
    InventoryLog,
    Notificacion,
    Pedido,
    PedidoDetalle,
    Product,
)
from .serializers import FacturaSerializer, PedidoSerializer, ProductSerializer
from .servicio_ia import (
    _formatear_contexto,
    _obtener_cliente,
    _tema_permitido,
    consultar_asistente_effiadmi,
)
from .soporte_pruebas import EffiBaseTestCase
from .utilidades import (
    _CorreoConLogo,
    _dominio_existe,
    autorizacion,
    assets_version,
    cargo_de_usuario,
    crear_notificacion,
    enviar_correo,
    validar_adjunto,
    validar_correo_electronico,
)


class ServicioIaCoberturaTest(SimpleTestCase):
    def test_temas_permitidos_y_bloqueados(self):
        self.assertTrue(_tema_permitido("Consulta de inventario"))
        self.assertFalse(_tema_permitido("programa una tarea"))
        self.assertFalse(_tema_permitido("python"))

    def test_formatear_contexto_vacio_y_con_datos(self):
        self.assertEqual(_formatear_contexto(None), "")
        texto = _formatear_contexto({"stock": "2 unidades"})
        self.assertIn("stock: 2 unidades", texto)
        self.assertIn("DATOS del negocio", texto)

    @patch.dict(os.environ, {"GEMINI_API_KEY": ""})
    def test_rechaza_tema_ajeno_sin_llamar_a_la_ia(self):
        with patch("effiadmi.servicio_ia._obtener_cliente") as cliente:
            respuesta = consultar_asistente_effiadmi("escribe un poema")
        self.assertIn("solo puedo ayudarte", respuesta)
        cliente.assert_not_called()

    @patch.dict(os.environ, {"GEMINI_API_KEY": ""})
    def test_sin_clave_devuelve_indicacion(self):
        respuesta = consultar_asistente_effiadmi("inventario")
        self.assertIn("No hay clave de Gemini", respuesta)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake"})
    def test_respuesta_con_contexto_y_contenido_vacio(self):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Respuesta"))]
        )
        with patch("effiadmi.servicio_ia._obtener_cliente", return_value=cliente):
            self.assertEqual(
                consultar_asistente_effiadmi("inventario", {"stock": "3"}),
                "Respuesta",
            )
            llamada = cliente.chat.completions.create.call_args.kwargs
            self.assertEqual(llamada["model"], "gemini-3.1-flash-lite")
            self.assertIn("stock: 3", llamada["messages"][0]["content"])

        cliente.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        )
        with patch("effiadmi.servicio_ia._obtener_cliente", return_value=cliente):
            respuesta = consultar_asistente_effiadmi("inventario")
        self.assertIn("politicas de contenido", respuesta)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake"})
    def test_error_del_cliente_devuelve_mensaje_generico(self):
        with patch(
            "effiadmi.servicio_ia._obtener_cliente", side_effect=RuntimeError("sin red")
        ):
            respuesta = consultar_asistente_effiadmi("inventario")
        self.assertIn("No pude procesar tu consulta", respuesta)
        self.assertNotIn("sin red", respuesta)

    @patch("effiadmi.servicio_ia.OpenAI")
    def test_cliente_se_crea_una_sola_vez(self, openai):
        import effiadmi.servicio_ia as servicio

        anterior = servicio._client
        servicio._client = None
        self.addCleanup(setattr, servicio, "_client", anterior)

        self.assertIs(_obtener_cliente(), _obtener_cliente())
        openai.assert_called_once()


class UtilidadesCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_crear_notificacion_acepta_id_y_lista_vacia(self):
        creadas = crear_notificacion(self.admin.id, "Aviso")
        self.assertEqual(len(creadas), 1)
        self.assertEqual(Notificacion.objects.get().usuario, self.admin)
        self.assertEqual(crear_notificacion([], "Aviso"), [])

    def test_cargo_de_usuario_sin_autenticacion(self):
        self.assertEqual(cargo_de_usuario(None), "")
        self.assertEqual(cargo_de_usuario(AnonymousUser()), "")

    def test_assets_version_ignora_archivos_inexistentes(self):
        with patch("pathlib.Path.stat", side_effect=OSError("sin archivo")):
            self.assertEqual(assets_version(None), {"assets_version": 0})

    def test_validar_adjunto_sin_archivo_valido_y_rechazado(self):
        self.assertEqual(validar_adjunto(None), (None, ""))

        pdf = SimpleUploadedFile("factura.pdf", b"%PDF-1.7 contenido")
        self.assertEqual(validar_adjunto(pdf), (pdf, ""))

        falso = SimpleUploadedFile("falso.pdf", b"no es pdf")
        self.assertIn("no coincide", validar_adjunto(falso)[1])

        with patch("effiadmi.utilidades.TAMANIO_MAX_ADJUNTO", 1):
            grande = SimpleUploadedFile("grande.pdf", b"%PDF")
            self.assertIn("supera el maximo", validar_adjunto(grande)[1])

        webp_malo = SimpleUploadedFile("imagen.webp", b"RIFF0000WAVE")
        self.assertIn("no coincide", validar_adjunto(webp_malo)[1])

        webp_bueno = SimpleUploadedFile("imagen.webp", b"RIFF0000WEBP")
        self.assertEqual(validar_adjunto(webp_bueno), (webp_bueno, ""))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_enviar_correo_en_modo_consola(self):
        exitoso, error = enviar_correo("destino@test.com", "Asunto", "Cuerpo")
        self.assertFalse(exitoso)
        self.assertIn("Modo prueba", error)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST_USER="",
    )
    @patch("effiadmi.utilidades._backend_es_consola", return_value=False)
    def test_enviar_correo_sin_configuracion(self, _mock):
        exitoso, error = enviar_correo("destino@test.com", "Asunto", "Cuerpo")
        self.assertFalse(exitoso)
        self.assertIn("SMTP no esta configurado", error)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST_USER="cuenta@test.com",
        DEFAULT_FROM_EMAIL="effi@test.com",
    )
    @patch("django.template.loader.render_to_string", return_value="<p>Cuerpo</p>")
    @patch("effiadmi.utilidades._CorreoConLogo.send", return_value=1)
    def test_enviar_correo_exitoso_y_rechazado_por_servidor(self, _send, _render):
        self.assertEqual(
            enviar_correo("destino@test.com", "Asunto", "Cuerpo"), (True, "")
        )
        with patch("effiadmi.utilidades._CorreoConLogo.send", return_value=0):
            exitoso, error = enviar_correo("destino@test.com", "Asunto", "Cuerpo")
        self.assertFalse(exitoso)
        self.assertIn("no confirmó", error)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST_USER="cuenta@test.com",
    )
    @patch("django.template.loader.render_to_string", side_effect=RuntimeError("fallo"))
    def test_enviar_correo_captura_excepciones(self, _render):
        exitoso, error = enviar_correo("destino@test.com", "Asunto", "Cuerpo")
        self.assertFalse(exitoso)
        self.assertEqual(error, "fallo")

    def test_correo_con_logo_sin_adjuntos(self):
        mensaje = _CorreoConLogo("Asunto", "Cuerpo", "effi@test.com", ["destino@test.com"])
        self.assertEqual(mensaje.attachments, [])
        self.assertIsNotNone(mensaje.message())

    def test_correo_con_adjunto_normal_e_inline(self):
        from email.mime.image import MIMEImage

        mensaje = _CorreoConLogo("Asunto", "Cuerpo", "effi@test.com", ["destino@test.com"])
        mensaje.attach("archivo.txt", "contenido")
        self.assertIsNotNone(mensaje.message())

        mensaje = _CorreoConLogo("Asunto", "Cuerpo", "effi@test.com", ["destino@test.com"])
        imagen = MIMEImage(b"\x89PNG\r\n\x1a\n", _subtype="png", name="logo.png")
        imagen.add_header("Content-ID", "<logo>")
        mensaje.attach(imagen)
        mensaje.attach("archivo.txt", "contenido")
        self.assertIsNotNone(mensaje.message())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST_USER="cuenta@test.com",
    )
    @patch("django.template.loader.render_to_string", return_value="<p>Cuerpo</p>")
    @patch("effiadmi.utilidades._CorreoConLogo.send", return_value=1)
    @patch("pathlib.Path.exists", return_value=False)
    def test_enviar_correo_sin_logo(self, _exists, _send, _render):
        self.assertEqual(
            enviar_correo("destino@test.com", "Asunto", "Cuerpo"), (True, "")
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST_USER="cuenta@test.com",
    )
    @patch("django.template.loader.render_to_string", return_value="<p>Cuerpo</p>")
    @patch("effiadmi.utilidades._CorreoConLogo.send", return_value=1)
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.read_bytes", side_effect=OSError("sin logo"))
    def test_enviar_correo_con_logo_ilegible(self, _read, _exists, _send, _render):
        self.assertEqual(
            enviar_correo("destino@test.com", "Asunto", "Cuerpo"), (True, "")
        )

    def test_validar_correo_rechaza_formatos_invalidos(self):
        self.assertIn("Escribe el correo", validar_correo_electronico("")[1])
        self.assertIn("demasiado largo", validar_correo_electronico("a" * 65 + "@x.com")[1])
        self.assertIn(
            "parte anterior", validar_correo_electronico("juan..perez@gmail.com")[1]
        )
        self.assertIn(
            "dominio del correo", validar_correo_electronico("juan@-gmail.com")[1]
        )
        self.assertIn(
            "extensión del correo", validar_correo_electronico("juan@gmail.c")[1]
        )

    @patch(
        "django.core.validators.validate_email",
        side_effect=ValidationError("invalido"),
    )
    def test_validar_correo_captura_error_de_django(self, _validar):
        self.assertIn("no es válido", validar_correo_electronico("juan@gmail.com")[1])

    @override_settings(VALIDAR_DOMINIO_CORREO=True)
    @patch("effiadmi.utilidades._dominio_existe", return_value=None)
    def test_validar_correo_extension_nueva_sin_dns(self, _dominio):
        exitoso, error = validar_correo_electronico("juan@dominio.zz")
        self.assertFalse(exitoso)
        self.assertIn("No se pudo comprobar", error)

    @override_settings(VALIDAR_DOMINIO_CORREO=True)
    def test_dominio_cacheado_se_reutiliza(self):
        cache.set("correo_dominio:ejemplo.com", True, 60)
        self.assertTrue(_dominio_existe("ejemplo.com"))

    @override_settings(VALIDAR_DOMINIO_CORREO=True)
    @patch("socket.getaddrinfo", side_effect=RuntimeError("fallo inesperado"))
    def test_dominio_error_inesperado_devuelve_none(self, _socket):
        self.assertIsNone(_dominio_existe("ejemplo.com"))

    def test_autorizacion_sincroniza_rol_desactualizado(self):
        self.iniciar_sesion(self.operador)
        session = self.client.session
        session["logueado"]["rol"] = "admin"
        session.modified = True
        session.save()

        @autorizacion()
        def vista(request):
            return HttpResponse("ok")

        request = RequestFactory().get("/")
        request.session = session
        self.assertEqual(vista(request).content, b"ok")
        self.assertEqual(session["logueado"]["rol"], "operador")


class SerializersCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.categoria = Categoria.objects.create(nombre="General")
        self.producto = Product.objects.create(
            sku="1", nombre="Cafe", precio_venta=5000, categoria=self.categoria
        )
        self.cliente = Cliente.objects.create(
            nombre="Cliente", correo="cliente@test.com", telefono="1", direccion="Calle"
        )
        self.factura = Factura.objects.create(
            cliente=self.cliente, usuario=self.admin, total=Decimal("5000")
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente, usuario=self.admin, total=Decimal("5000")
        )
        PedidoDetalle.objects.create(
            pedido=self.pedido,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal("5000"),
        )

    def test_product_serializer_crea_sucursal_principal_sin_kardex(self):
        Branch.objects.all().delete()
        serializer = ProductSerializer(
            data={
                "sku": "2",
                "nombre": "Te",
                "precio_venta": "4000",
                "categoria": self.categoria.id,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        product = serializer.save()

        branch = Branch.objects.get(es_principal=True)
        inventario = Inventory.objects.get(product=product, branch=branch)
        self.assertEqual(inventario.cantidad_disponible, 0)
        self.assertFalse(InventoryLog.objects.filter(inventory=inventario).exists())

    def test_factura_no_permite_reasignar_cliente_sin_admin(self):
        request = SimpleNamespace(user=self.operador)
        serializer = FacturaSerializer(
            instance=self.factura,
            data={"cliente": self.cliente.id},
            partial=True,
            context={"request": request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("Solo un administrador", str(serializer.errors))

    def test_factura_no_permite_editar_detalles(self):
        with self.assertRaises(serializers.ValidationError):
            FacturaSerializer().update(self.factura, {"detalles": []})

    def test_factura_admin_actualiza_cabecera_sin_detalles(self):
        cliente_nuevo = Cliente.objects.create(
            nombre="Cliente Nuevo",
            correo="nuevo@test.com",
            telefono="2",
            direccion="Calle 2",
        )
        request = SimpleNamespace(user=self.admin)
        serializer = FacturaSerializer(
            instance=self.factura,
            data={"cliente": cliente_nuevo.id},
            partial=True,
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.factura.refresh_from_db()
        self.assertEqual(self.factura.cliente, cliente_nuevo)

    def test_pedido_no_permite_reasignar_cliente_sin_admin(self):
        request = SimpleNamespace(user=self.operador)
        serializer = PedidoSerializer(
            instance=self.pedido,
            data={"cliente": self.cliente.id},
            partial=True,
            context={"request": request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("Solo un administrador", str(serializer.errors))

    def test_pedido_actualiza_detalles_y_recalcula_total(self):
        producto_nuevo = Product.objects.create(
            sku="2", nombre="Te", precio_venta=4000, categoria=self.categoria
        )
        request = SimpleNamespace(user=self.admin)
        serializer = PedidoSerializer(
            instance=self.pedido,
            data={
                "cliente": self.cliente.id,
                "detalles": [
                    {
                        "producto": producto_nuevo.id,
                        "cantidad": 2,
                        "precio_unitario": "4000",
                    }
                ],
            },
            partial=True,
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.total, Decimal("8000"))
        self.assertEqual(self.pedido.detalles.count(), 1)
        self.assertEqual(self.pedido.detalles.get().producto, producto_nuevo)

    def test_pedido_actualiza_sin_detalles_y_conserva_lineas(self):
        request = SimpleNamespace(user=self.admin)
        serializer = PedidoSerializer(
            instance=self.pedido,
            data={"cliente": self.cliente.id},
            partial=True,
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.detalles.count(), 1)
        self.assertEqual(self.pedido.total, Decimal("5000"))
