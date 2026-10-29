"""Pruebas de las vistas con sesion (permisos, CRUD, inventario, pedidos, usuarios)."""

from datetime import date
from decimal import Decimal
import json
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from .models import (
    Branch,
    Categoria,
    Cliente,
    CorreoEnviado,
    Factura,
    FacturaCompra,
    FacturaDetalle,
    Inventory,
    InventoryLog,
    Notificacion,
    Pedido,
    Product,
    Proveedor,
    Reporte,
    UserProfile,
)
from .soporte_pruebas import EffiBaseTestCase, textos_mensajes


class CorreosTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.url = reverse("effiadmi:lista_correos")

    @patch("effiadmi.views.enviar_correo", return_value=(True, ""))
    def test_envia_correo_y_guarda_el_resultado(self, enviar_correo):
        respuesta = self.client.post(
            self.url,
            {
                "accion": "enviar",
                "destinatario": "cliente@test.com",
                "asunto": "Actualizacion del pedido",
                "cuerpo": "Tu pedido esta listo.",
            },
            follow=True,
        )

        enviar_correo.assert_called_once_with(
            "cliente@test.com", "Actualizacion del pedido", "Tu pedido esta listo."
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            CorreoEnviado.objects.filter(
                destinatario="cliente@test.com", exitoso=True
            ).exists()
        )

    @patch(
        "effiadmi.views.enviar_correo",
        return_value=(False, "No se pudo conectar con el servidor SMTP."),
    )
    def test_muestra_el_motivo_del_fallo_de_envio(self, enviar_correo):
        respuesta = self.client.post(
            self.url,
            {
                "accion": "enviar",
                "destinatario": "cliente@test.com",
                "asunto": "Prueba de envio",
                "cuerpo": "Mensaje de prueba.",
            },
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No se pudo conectar con el servidor SMTP.")
        self.assertFalse(CorreoEnviado.objects.get().exitoso)

    @patch("effiadmi.views.enviar_correo")
    @patch(
        "effiadmi.views.generar_borrador_correo",
        return_value="Hola, te compartimos la informacion solicitada.",
    )
    def test_borrador_ia_se_muestra_y_no_se_envia(
        self, generar_borrador, enviar_correo
    ):
        respuesta = self.client.post(
            self.url,
            {
                "accion": "borrador_ia",
                "destinatario": "cliente@test.com",
                "asunto": "Informacion del pedido",
                "instrucciones_borrador": "Informar que el pedido esta listo.",
            },
        )

        generar_borrador.assert_called_once_with(
            "Informar que el pedido esta listo.", "Informacion del pedido"
        )
        enviar_correo.assert_not_called()
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Hola, te compartimos la informacion solicitada.")
        self.assertContains(respuesta, "Borrador generado.")
        self.assertEqual(CorreoEnviado.objects.count(), 0)

    @patch("effiadmi.views.generar_borrador_correo")
    def test_borrador_ia_requiere_instrucciones(self, generar_borrador):
        respuesta = self.client.post(
            self.url,
            {"accion": "borrador_ia", "instrucciones_borrador": ""},
        )

        generar_borrador.assert_not_called()
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Describe brevemente el correo")

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    @patch("effiadmi.servicio_ia._obtener_cliente")
    def test_borrador_informa_si_gemini_rechaza_la_clave(self, obtener_cliente):
        from openai import AuthenticationError

        from .servicio_ia import generar_borrador_correo

        cliente = Mock()
        cliente.chat.completions.create.side_effect = AuthenticationError(
            "unauthorized",
            response=Mock(status_code=401),
            body=None,
        )
        obtener_cliente.return_value = cliente

        with self.assertRaisesRegex(RuntimeError, "Gemini rechazo la clave"):
            generar_borrador_correo("Informar sobre una consulta", "Actualizacion")

    def test_smtp_no_se_considera_configurado_sin_password_o_con_backend_consola(self):
        from .utilidades import _correo_configurado

        with override_settings(
            EMAIL_HOST_USER="sender@test.com",
            EMAIL_HOST_PASSWORD="",
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        ):
            self.assertFalse(_correo_configurado())
        with override_settings(
            EMAIL_HOST_USER="sender@test.com",
            EMAIL_HOST_PASSWORD="not-empty",
            EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        ):
            self.assertFalse(_correo_configurado())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST_USER="sender@test.com",
        EMAIL_HOST_PASSWORD="configured-for-test",
    )
    def test_utilidad_envia_correo_con_backend_de_prueba(self):
        from .utilidades import enviar_correo

        exitoso, error = enviar_correo(
            "cliente@test.com", "Asunto de prueba", "Mensaje de prueba."
        )

        self.assertTrue(exitoso, error)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["cliente@test.com"])
        self.assertEqual(mail.outbox[0].subject, "Asunto de prueba")


class ClienteCorreoDuplicadoTest(TransactionTestCase):
    """Con TransactionTestCase (sin el atomic de TestCase) se reproduce el
    entorno real de autocommit: la vista captura el IntegrityError y sigue
    funcionando. Bajo TestCase la transaccion quedaria rota."""

    def test_correo_duplicado_no_crea_segundo_cliente(self):
        Branch.objects.create(nombre="Principal", es_principal=True)
        Cliente.objects.create(nombre="A", correo="dup@test.com", telefono="1", direccion="x")
        user = User.objects.create_user(username="op@test.com", password="ClaveSegura123!")
        UserProfile.objects.create(user=user, cargo="operador")
        session = self.client.session
        session["logueado"] = {"id": user.id, "nombre": "Op", "rol": "operador"}
        session.save()

        self.client.post(
            reverse("effiadmi:crear_cliente"),
            {"nombre": "Otro", "correo": "dup@test.com", "telefono": "3000000000", "direccion": "x"},
        )
        self.assertEqual(Cliente.objects.filter(correo="dup@test.com").count(), 1)


class PermisosTest(EffiBaseTestCase):
    def test_anonimo_redirige_a_login_con_next(self):
        respuesta = self.client.get(reverse("effiadmi:lista_clientes"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.startswith(reverse("effiadmi:login")))
        self.assertIn("next=", respuesta.url)

    def test_operador_no_entra_a_la_seccion_de_usuarios(self):
        self.iniciar_sesion(self.operador)
        respuesta = self.client.get(reverse("effiadmi:lista_usuarios"))
        self.assertRedirects(respuesta, reverse("effiadmi:inicio"))

    def test_operador_no_puede_crear_productos(self):
        self.iniciar_sesion(self.operador)
        respuesta = self.client.get(reverse("effiadmi:crear_producto"))
        self.assertRedirects(respuesta, reverse("effiadmi:inicio"))

    def test_admin_si_entra_a_usuarios(self):
        self.iniciar_sesion(self.admin)
        respuesta = self.client.get(reverse("effiadmi:lista_usuarios"))
        self.assertEqual(respuesta.status_code, 200)

    def test_cuenta_desactivada_pierde_la_sesion(self):
        self.iniciar_sesion(self.operador)
        self.operador.is_active = False
        self.operador.save(update_fields=["is_active"])
        respuesta = self.client.get(reverse("effiadmi:inicio"))
        self.assertRedirects(respuesta, reverse("effiadmi:login"))
        self.assertNotIn("logueado", self.client.session)

    def test_dashboard_responde_200(self):
        self.iniciar_sesion(self.admin)
        self.assertEqual(self.client.get(reverse("effiadmi:inicio")).status_code, 200)

    def test_perfil_responde_200(self):
        self.iniciar_sesion(self.operador)
        self.assertEqual(self.client.get(reverse("effiadmi:perfil")).status_code, 200)


class ClientesTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.operador)

    def test_operador_crea_cliente(self):
        respuesta = self.client.post(
            reverse("effiadmi:crear_cliente"),
            {"nombre": "Juan", "correo": "juan@test.com", "telefono": "3000000000", "direccion": "Calle"},
            follow=True,
        )
        self.assertTrue(Cliente.objects.filter(correo="juan@test.com").exists())
        self.assertIn("¡Cliente creado exitosamente!", textos_mensajes(respuesta))

    def test_campos_incompletos_no_crean_cliente(self):
        self.client.post(reverse("effiadmi:crear_cliente"), {"nombre": "Sin correo"})
        self.assertEqual(Cliente.objects.count(), 0)

    def test_admin_edita_cliente(self):
        cliente = self.crear_cliente()
        self.iniciar_sesion(self.admin)
        self.client.post(
            reverse("effiadmi:editar_cliente", args=[cliente.id]),
            {"nombre": "Editado", "correo": cliente.correo, "telefono": "9000000", "direccion": "Y"},
            follow=True,
        )
        cliente.refresh_from_db()
        self.assertEqual(cliente.nombre, "Editado")

    def test_eliminar_cliente_alterna_activo(self):
        cliente = self.crear_cliente()
        self.iniciar_sesion(self.admin)
        self.client.post(reverse("effiadmi:eliminar_cliente", args=[cliente.id]), follow=True)
        cliente.refresh_from_db()
        self.assertFalse(cliente.activo)
        self.client.post(reverse("effiadmi:eliminar_cliente", args=[cliente.id]), follow=True)
        cliente.refresh_from_db()
        self.assertTrue(cliente.activo)


class EstadisticasIATest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    def test_graficas_usen_ventas_y_movimientos_reales(self):
        categoria = Categoria.objects.create(nombre="Abarrotes")
        producto = Product.objects.create(
            sku="32001",
            nombre="Arroz",
            precio_venta=2500,
            categoria=categoria,
        )
        inventario = Inventory.objects.create(
            product=producto,
            branch=self.branch,
            cantidad_disponible=2,
            stock_minimo=3,
        )
        cliente = Cliente.objects.create(
            nombre="Cliente",
            correo="cliente.graficas@test.com",
            telefono="300",
            direccion="Calle 1",
        )
        factura = Factura.objects.create(
            cliente=cliente,
            usuario=self.admin,
            estado="emitida",
        )
        FacturaDetalle.objects.create(
            factura=factura,
            producto=producto,
            cantidad=7,
            precio_unitario=2500,
            subtotal=17500,
        )
        for tipo in ("ENTRADA", "SALIDA", "AJUSTE"):
            InventoryLog.objects.create(
                inventory=inventario,
                tipo_movimiento=tipo,
                cantidad=1,
                cantidad_resultante=inventario.cantidad_disponible,
                usuario=self.admin,
            )

        respuesta = self.client.get(reverse("effiadmi:estadisticas_ia"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            json.loads(respuesta.context["top_productos_labels_json"]),
            ["Arroz"],
        )
        self.assertEqual(
            json.loads(respuesta.context["top_productos_valores_json"]),
            [7],
        )
        self.assertEqual(
            json.loads(respuesta.context["movimientos_valores_json"]),
            [1, 1, 1],
        )
        self.assertEqual(respuesta.context["productos_bajos"][0].id, inventario.id)
        self.assertContains(respuesta, "Reposición sugerida")

    def test_graficas_sin_datos_muestran_estado_vacio(self):
        respuesta = self.client.get(reverse("effiadmi:estadisticas_ia"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No hay ventas registradas")
        self.assertContains(respuesta, "No hay movimientos de inventario")


class NotificacionesStockTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        producto, self.inventario = self.crear_producto(
            sku="65001",
            nombre="Leche",
            precio=2000,
            stock=2,
            stock_minimo=5,
        )
        self.producto = producto

    @patch(
        "effiadmi.servicio_ia.generar_recomendacion_stock",
        return_value="Programa una reposicion.",
    )
    def test_stock_bajo_genera_notificacion_ia_con_cifras_reales(self, generar):
        from .utilidades import notificar_stock_bajo

        notificar_stock_bajo(self.inventario, cantidad_anterior=6)

        generar.assert_called_once_with("Leche", 2, 5, self.branch.nombre)
        notificaciones = Notificacion.objects.filter(
            enlace=f"inventario/{self.inventario.id}/"
        )
        self.assertEqual(notificaciones.count(), 2)
        self.assertTrue(
            all(
                "Stock actual: 2; stock minimo: 5." in notificacion.mensaje
                and "Programa una reposicion." in notificacion.mensaje
                for notificacion in notificaciones
            )
        )

    @patch(
        "effiadmi.servicio_ia.generar_recomendacion_stock",
        return_value="Programa una reposicion.",
    )
    def test_no_duplica_alerta_y_la_cierra_al_reponer(self, generar):
        from .utilidades import notificar_stock_bajo

        notificar_stock_bajo(self.inventario, cantidad_anterior=6)
        notificar_stock_bajo(self.inventario, cantidad_anterior=2)
        self.assertEqual(Notificacion.objects.count(), 2)
        generar.assert_called_once()

        self.inventario.cantidad_disponible = 8
        self.inventario.save(update_fields=["cantidad_disponible"])
        notificar_stock_bajo(self.inventario, cantidad_anterior=2)

        self.assertFalse(
            Notificacion.objects.filter(leido=False).exists()
        )

    @patch(
        "effiadmi.servicio_ia.generar_recomendacion_stock",
        side_effect=RuntimeError("IA no disponible"),
    )
    def test_falla_ia_no_impide_notificar_stock_bajo(self, generar):
        from .utilidades import notificar_stock_bajo

        with self.assertLogs("effiadmi.utilidades", level="ERROR") as registros:
            notificar_stock_bajo(self.inventario)

        generar.assert_called_once()
        self.assertIn("No se pudo generar la recomendacion IA", registros.output[0])
        self.assertEqual(Notificacion.objects.count(), 2)
        self.assertTrue(
            all(
                "stock actual: 2" in notificacion.mensaje.lower()
                and "programa la reposicion" in notificacion.mensaje.lower()
                for notificacion in Notificacion.objects.all()
            )
        )


class ProductosTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        from .models import Categoria

        self.categoria = Categoria.objects.create(nombre="Abarrotes")

    def _post(self, **extra):
        datos = {
            "nombre": "Arroz",
            "descripcion": "libra",
            "categoria": self.categoria.id,
            "precio_venta": "3000",
            "sucursal": self.branch.id,
            "stock_inicial": "10",
            "stock_minimo": "3",
        }
        datos.update(extra)
        return self.client.post(reverse("effiadmi:crear_producto"), datos, follow=True)

    def test_crear_producto_crea_inventario_y_kardex(self):
        self._post()
        producto = Product.objects.get(nombre="Arroz")
        self.assertEqual(producto.sku, "1")
        inventario = Inventory.objects.get(product=producto, branch=self.branch)
        self.assertEqual(inventario.cantidad_disponible, 10)
        self.assertTrue(
            InventoryLog.objects.filter(inventory=inventario, tipo_movimiento="ENTRADA").exists()
        )

    def test_precio_con_decimales_es_rechazado(self):
        self._post(precio_venta="3000.50")
        self.assertFalse(Product.objects.filter(nombre="Arroz").exists())

    def test_precio_fuera_de_rango_es_rechazado(self):
        self._post(precio_venta="500")
        self.assertFalse(Product.objects.filter(nombre="Arroz").exists())

    def test_categoria_invalida_es_rechazada(self):
        self._post(categoria="")
        self.assertFalse(Product.objects.filter(nombre="Arroz").exists())

    def test_siguiente_sku_incrementa(self):
        self._post()
        self._post(nombre="Frijol")
        self.assertTrue(Product.objects.filter(sku="2", nombre="Frijol").exists())


class InventarioMovimientoTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.operador)
        self.producto, self.inventario = self.crear_producto(stock=10, stock_minimo=2)
        self.url = reverse("effiadmi:registrar_movimiento", args=[self.inventario.id])

    def test_entrada_suma_stock(self):
        self.client.post(self.url, {"tipo_movimiento": "ENTRADA", "cantidad": "5", "motivo": "compra"})
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 15)
        self.assertTrue(InventoryLog.objects.filter(inventory=self.inventario, tipo_movimiento="ENTRADA").exists())

    def test_salida_con_stock_insuficiente_no_cambia_nada(self):
        self.client.post(self.url, {"tipo_movimiento": "SALIDA", "cantidad": "50"})
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 10)
        self.assertFalse(InventoryLog.objects.filter(inventory=self.inventario, tipo_movimiento="SALIDA").exists())

    def test_ajuste_fija_el_stock(self):
        self.client.post(self.url, {"tipo_movimiento": "AJUSTE", "cantidad": "7"})
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 7)

    def test_cantidad_cero_es_rechazada(self):
        self.client.post(self.url, {"tipo_movimiento": "ENTRADA", "cantidad": "0"})
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 10)

    def test_tipo_invalido_es_rechazado(self):
        self.client.post(self.url, {"tipo_movimiento": "ROBO", "cantidad": "1"})
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 10)


class PedidosTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.operador)
        self.producto, self.inventario = self.crear_producto(precio=2000, stock=10)
        self.cliente = self.crear_cliente()

    def _crear_pedido(self, cantidad="2"):
        self.client.post(
            reverse("effiadmi:crear_pedido"),
            {"cliente": self.cliente.id, "producto": [self.producto.id], "cantidad": [cantidad]},
            follow=True,
        )
        return Pedido.objects.latest("id")

    def test_crear_pedido_calcula_total_y_notifica(self):
        pedido = self._crear_pedido(cantidad="3")
        self.assertEqual(pedido.estado, "pendiente")
        self.assertEqual(pedido.total, Decimal("6000.00"))
        self.assertEqual(pedido.detalles.count(), 1)
        self.assertTrue(Notificacion.objects.filter(usuario=self.admin).exists())

    def test_pedido_sin_productos_es_rechazado(self):
        self.client.post(reverse("effiadmi:crear_pedido"), {"cliente": self.cliente.id})
        self.assertEqual(Pedido.objects.count(), 0)

    def test_confirmar_descuenta_stock(self):
        pedido = self._crear_pedido(cantidad="4")
        self.client.post(reverse("effiadmi:confirmar_pedido", args=[pedido.id]), follow=True)
        pedido.refresh_from_db()
        self.inventario.refresh_from_db()
        self.assertEqual(pedido.estado, "confirmado")
        self.assertEqual(self.inventario.cantidad_disponible, 6)

    def test_confirmar_sin_stock_no_cambia(self):
        pedido = self._crear_pedido(cantidad="50")
        self.client.post(reverse("effiadmi:confirmar_pedido", args=[pedido.id]), follow=True)
        pedido.refresh_from_db()
        self.inventario.refresh_from_db()
        self.assertEqual(pedido.estado, "pendiente")
        self.assertEqual(self.inventario.cantidad_disponible, 10)

    def test_pagar_emite_factura(self):
        pedido = self._crear_pedido(cantidad="2")
        self.client.post(reverse("effiadmi:confirmar_pedido", args=[pedido.id]), follow=True)
        self.client.post(reverse("effiadmi:pagar_pedido", args=[pedido.id]), follow=True)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "pagado")
        factura = Factura.objects.get(pedido=pedido)
        self.assertEqual(factura.estado, "emitida")
        self.assertEqual(factura.total, Decimal("4000.00"))
        self.assertEqual(factura.detalles.count(), 1)

    def test_cancelar_confirmado_devuelve_stock(self):
        pedido = self._crear_pedido(cantidad="3")
        self.client.post(reverse("effiadmi:confirmar_pedido", args=[pedido.id]), follow=True)
        self.client.post(reverse("effiadmi:cancelar_pedido", args=[pedido.id]), follow=True)
        pedido.refresh_from_db()
        self.inventario.refresh_from_db()
        self.assertEqual(pedido.estado, "cancelado")
        self.assertEqual(self.inventario.cantidad_disponible, 10)

    def test_admin_elimina_pedido_pendiente(self):
        pedido = self._crear_pedido()
        self.iniciar_sesion(self.admin)
        self.client.post(reverse("effiadmi:eliminar_pedido", args=[pedido.id]), follow=True)
        self.assertFalse(Pedido.objects.filter(id=pedido.id).exists())


class UsuariosTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    def test_crear_usuario_valido(self):
        self.client.post(
            reverse("effiadmi:crear_usuario"),
            {
                "nombre_usuario": "Nuevo",
                "apellido_usuario": "Oper",
                "email": "nuevo@test.com",
                "contraseña": "ClaveRobusta2026!",
                "cargo": "operador",
            },
            follow=True,
        )
        user = User.objects.filter(username="nuevo@test.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.profile.cargo, "operador")
        self.assertTrue(user.check_password("ClaveRobusta2026!"))

    def test_password_debil_es_rechazada(self):
        self.client.post(
            reverse("effiadmi:crear_usuario"),
            {"nombre_usuario": "Debil", "email": "debil@test.com", "contraseña": "123456", "cargo": "operador"},
        )
        self.assertFalse(User.objects.filter(username="debil@test.com").exists())

    def test_correo_duplicado_es_rechazado(self):
        self.client.post(
            reverse("effiadmi:crear_usuario"),
            {"nombre_usuario": "Dup", "email": self.admin.email, "contraseña": "ClaveRobusta2026!", "cargo": "admin"},
        )
        self.assertEqual(User.objects.filter(email=self.admin.email).count(), 1)

    def test_editar_usuario_con_password_debil_es_rechazado(self):
        self.client.post(
            reverse("effiadmi:editar_usuario", args=[self.operador.id]),
            {"nombre_usuario": "Op", "apellido_usuario": "X", "email": self.operador.email, "cargo": "operador", "contraseña": "123456"},
        )
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.check_password("ClaveSegura123!"))

    def test_no_puede_desactivar_su_propia_cuenta(self):
        respuesta = self.client.post(
            reverse("effiadmi:eliminar_usuario", args=[self.admin.id]), follow=True
        )
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertIn("No puedes desactivar tu propia cuenta.", textos_mensajes(respuesta))

    def test_desactiva_otra_cuenta(self):
        self.client.post(reverse("effiadmi:eliminar_usuario", args=[self.operador.id]), follow=True)
        self.operador.refresh_from_db()
        self.assertFalse(self.operador.is_active)


class ProveedoresTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    def test_pestanas_de_estado_y_busqueda_filtran_proveedores(self):
        activo = Proveedor.objects.create(
            nombre="Proveedor activo",
            correo="activo@proveedores.test",
            telefono="111",
            direccion="Calle 1",
        )
        inactivo = Proveedor.objects.create(
            nombre="Proveedor inactivo",
            correo="inactivo@proveedores.test",
            telefono="222",
            direccion="Calle 2",
            activo=False,
        )

        respuesta_activos = self.client.get(
            reverse("effiadmi:lista_proveedores"),
            {"estado": "activo", "q": "proveedor"},
        )
        respuesta_inactivos = self.client.get(
            reverse("effiadmi:lista_proveedores"),
            {"estado": "inactivo", "q": "proveedor"},
        )

        self.assertEqual(respuesta_activos.status_code, 200)
        self.assertEqual(
            list(respuesta_activos.context["proveedores"]), [activo]
        )
        self.assertEqual(
            list(respuesta_inactivos.context["proveedores"]), [inactivo]
        )
        self.assertEqual(respuesta_activos.context["total_cuenta"], 2)
        self.assertEqual(respuesta_activos.context["activos_cuenta"], 1)

    def test_lista_muestra_acciones_en_grupo_con_espaciado(self):
        proveedor = Proveedor.objects.create(
            nombre="Proveedor de prueba",
            correo="acciones@proveedores.test",
            telefono="111",
            direccion="Calle 1",
        )

        respuesta = self.client.get(reverse("effiadmi:lista_proveedores"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'class="table-actions"')
        self.assertContains(respuesta, reverse("effiadmi:detalle_proveedor", args=[proveedor.id]))
        self.assertContains(respuesta, reverse("effiadmi:editar_proveedor", args=[proveedor.id]))

    def test_resumen_muestra_totales_reales_de_proveedores_y_compras(self):
        proveedor = Proveedor.objects.create(
            nombre="Proveedor resumen",
            correo="resumen@proveedores.test",
            telefono="333",
            direccion="Calle 3",
        )
        Proveedor.objects.create(
            nombre="Proveedor inactivo",
            correo="inactivo.resumen@proveedores.test",
            telefono="444",
            direccion="Calle 4",
            activo=False,
        )
        FacturaCompra.objects.create(
            proveedor=proveedor,
            usuario=self.admin,
            numero="COMP-RESUMEN",
            fecha=date(2026, 10, 1),
            monto=Decimal("125000"),
        )
        FacturaCompra.objects.create(
            proveedor=None,
            usuario=self.admin,
            numero="COMP-SIN-PROVEEDOR",
            fecha=date(2026, 10, 2),
            monto=Decimal("50000"),
        )

        respuesta = self.client.get(reverse("effiadmi:lista_proveedores"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["total_cuenta"], 2)
        self.assertEqual(respuesta.context["activos_cuenta"], 1)
        self.assertEqual(respuesta.context["total_compras"], Decimal("125000"))
        self.assertContains(respuesta, "Total de compras")

    def test_crear_proveedor(self):
        self.client.post(
            reverse("effiadmi:crear_proveedor"),
            {"nombre_proveedor": "Prov", "correo": "prov@test.com", "telefono": "3000000000", "direccion": "Calle"},
            follow=True,
        )
        self.assertTrue(Proveedor.objects.filter(correo="prov@test.com").exists())

    def test_eliminar_proveedor_alterna_activo(self):
        proveedor = Proveedor.objects.create(nombre="P", correo="p@test.com", telefono="1", direccion="x")
        self.client.post(reverse("effiadmi:eliminar_proveedor", args=[proveedor.id]), follow=True)
        proveedor.refresh_from_db()
        self.assertFalse(proveedor.activo)


class FacturasCompraExportTest(EffiBaseTestCase):
    """Regresion: la exportacion a Excel reventaba con un ValueError.

    `_aplicar_filtros_facturas_compra` devuelve 4 valores y la vista los
    desempaquetaba en 3; la excepcion quedaba tragada y el boton entregaba un
    redirect en lugar del archivo. Aqui se exige el xlsx real con y sin
    filtros.
    """

    MIME_XLSX = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.proveedor = Proveedor.objects.create(
            nombre="Distribuidora", correo="dist@test.com", telefono="1", direccion="x"
        )
        FacturaCompra.objects.create(
            proveedor=self.proveedor,
            usuario=self.admin,
            numero="FC-001",
            fecha=date.today(),
            monto=150000,
        )

    def test_exporta_un_xlsx_valido(self):
        respuesta = self.client.get(
            reverse("effiadmi:exportar_facturas_compra_excel")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], self.MIME_XLSX)
        self.assertEqual(
            respuesta.content[:2],
            b"PK",
            "El archivo no es un xlsx (zip) valido",
        )

    def test_exporta_con_cada_filtro(self):
        consultas = [
            "",
            "?q=FC-001",
            "?q=inexistente",
            "?mes=2026-10",
            "?mes=1999-01",
            f"?proveedor={self.proveedor.id}",
            "?proveedor=999999",
            "?q=FC&mes=2026-10&proveedor=" + str(self.proveedor.id),
        ]
        for consulta in consultas:
            with self.subTest(consulta=consulta or "(sin filtros)"):
                respuesta = self.client.get(
                    reverse("effiadmi:exportar_facturas_compra_excel") + consulta
                )
                self.assertEqual(respuesta.status_code, 200, consulta)
                self.assertEqual(respuesta["Content-Type"], self.MIME_XLSX, consulta)
                self.assertTrue(respuesta.content.startswith(b"PK"), consulta)


class FacturacionUIActionsTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.cliente = Cliente.objects.create(
            nombre="Cliente facturacion",
            correo="facturacion.ui@test.com",
            telefono="300",
            direccion="Calle 1",
        )

    def test_filtros_de_facturas_se_muestran_y_filtran(self):
        emitida = Factura.objects.create(
            cliente=self.cliente,
            usuario=self.admin,
            estado="emitida",
        )
        anulada = Factura.objects.create(
            cliente=self.cliente,
            usuario=self.admin,
            estado="anulada",
        )

        respuesta = self.client.get(
            reverse("effiadmi:facturacion"),
            {"tab": "ventas", "estado": "emitida"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            list(respuesta.context["facturas"].values_list("id", flat=True)),
            [emitida.id],
        )
        self.assertContains(respuesta, 'class="table-actions"')
        self.assertContains(respuesta, "filter-card")
        self.assertContains(respuesta, "Emitidas")
        self.assertNotContains(respuesta, f"#{anulada.id}")


class ReportesUIActionsTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    def test_filtros_y_acciones_tienen_grupos_con_espaciado(self):
        reporte = Reporte.objects.create(
            usuario=self.operador,
            titulo="Reporte para probar acciones",
            descripcion="Descripcion",
        )

        respuesta = self.client.get(
            reverse("effiadmi:reportes"),
            {"estado": "pendiente"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context["reportes"]), [reporte])
        self.assertContains(respuesta, "toolbar-filters")
        self.assertContains(respuesta, "filter-actions")
        self.assertContains(respuesta, "table-actions")
