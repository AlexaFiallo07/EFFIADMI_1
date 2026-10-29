"""Regression tests for the fixes applied before the delivery.

Covers:
1. crear_cliente / editar_cliente no longer crash with NameError ('re').
2. crear_proveedor / editar_proveedor ditto.
3. Forms keep the user's typed data when a validation fails.
4. anular_factura cancels the paid pedido and returns its stock
   (previously the user was trapped in a cancel/annul loop).
5. eliminar_categoria works for empty categories.
6. Searches by id accept numeric queries and keep working for names.
7. registrar_movimiento accepts AJUSTE with amount 0 (stock ran out),
   while ENTRADA/SALIDA keep rejecting it.

Run: venv\\Scripts\\python.exe manage.py test effiadmi.tests_correcciones
"""

from django.urls import reverse

from .models import (
    Branch,
    Categoria,
    Cliente,
    Factura,
    Inventory,
    InventoryLog,
    Pedido,
    PedidoDetalle,
    Product,
    Proveedor,
)
from .soporte_pruebas import EffiBaseTestCase
from .views import _motivo_salida_confirmacion


class CorreccionClientesProveedores(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    def test_crear_cliente_valido_exito(self):
        resp = self.client.post(reverse("effiadmi:crear_cliente"), {
            "nombre": "Juan Perez",
            "correo": "juan@example.com",
            "telefono": "3001112233",
            "direccion": "Calle falsa 123",
        }, follow=True)
        self.assertEqual(Cliente.objects.filter(correo="juan@example.com").count(), 1)
        self.assertIn("exitosamente", [str(m) for m in resp.context["messages"]][0])

    def test_editar_cliente_valido_exito(self):
        cliente = Cliente.objects.create(
            nombre="Original", correo="orig@mail.com",
            telefono="3005559999", direccion="Calle 5",
        )
        resp = self.client.post(
            reverse("effiadmi:editar_cliente", args=[cliente.id]),
            {
                "nombre": "Original Editado",
                "correo": "orig@mail.com",
                "telefono": "3005559999",
                "direccion": "Calle 5",
            },
            follow=True,
        )
        cliente.refresh_from_db()
        self.assertEqual(cliente.nombre, "Original Editado")

    def test_editar_proveedor_valido_exito(self):
        prov = Proveedor.objects.create(
            nombre="Distribuidora X",
            correo="x@proveedor.com",
            telefono="3001110000",
            direccion="Calle 9",
        )
        resp = self.client.post(
            reverse("effiadmi:editar_proveedor", args=[prov.id]),
            {
                "nombre_proveedor": "Distribuidora X Editada",
                "correo": "x@proveedor.com",
                "telefono": "3001110000",
                "direccion": "Calle 9 Editada",
            },
            follow=True,
        )
        prov.refresh_from_db()
        self.assertEqual(prov.nombre, "Distribuidora X Editada")
        self.assertEqual(prov.direccion, "Calle 9 Editada")

    def test_crear_cliente_telefono_invalido_conserva_los_datos(self):
        resp = self.client.post(reverse("effiadmi:crear_cliente"), {
            "nombre": "Juan Perez",
            "correo": "juan2@example.com",
            "telefono": "abc",
            "direccion": "Calle falsa 123",
        })
        self.assertContains(resp, 'value="Juan Perez"')
        self.assertContains(resp, 'value="juan2@example.com"')

    def test_crear_proveedor_telefono_invalido_conserva_los_datos(self):
        resp = self.client.post(reverse("effiadmi:crear_proveedor"), {
            "nombre_proveedor": "Distribuidora Y",
            "correo": "y@proveedor.com",
            "telefono": "abc",
            "direccion": "Calle 9",
        })
        self.assertContains(resp, 'value="Distribuidora Y"')

    def test_editar_proveedor_telefono_invalido_conserva_los_datos(self):
        prov = Proveedor.objects.create(
            nombre="Distribuidora Z",
            correo="z@proveedor.com",
            telefono="3001110000",
            direccion="Calle 9",
        )
        resp = self.client.post(
            reverse("effiadmi:editar_proveedor", args=[prov.id]),
            {
                "nombre_proveedor": "Distribuidora Z Editada",
                "correo": "z@proveedor.com",
                "telefono": "abc",
                "direccion": "Calle 9",
            },
        )
        self.assertContains(resp, 'value="Distribuidora Z Editada"')


class CorreccionEliminarCategoria(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    def test_eliminar_categoria_vacia(self):
        cat = Categoria.objects.create(nombre="Categoria Vacia Test")
        resp = self.client.post(reverse("effiadmi:eliminar_categoria", args=[cat.id]), follow=True)
        self.assertFalse(Categoria.objects.filter(pk=cat.pk).exists())
        self.assertTrue(
            any("eliminada" in str(m) for m in resp.context["messages"])
        )

    def test_eliminar_categoria_con_productos_bloqueada(self):
        cat = Categoria.objects.create(nombre="Con Productos")
        producto = Product.objects.create(
            sku="SKU-CAT", nombre="Producto Bloqueo",
            precio_venta=1000, categoria=cat,
        )
        resp = self.client.post(reverse("effiadmi:eliminar_categoria", args=[cat.id]), follow=True)
        self.assertTrue(Categoria.objects.filter(pk=cat.pk).exists())
        self.assertTrue(
            any("No se puede eliminar" in str(m) for m in resp.context["messages"])
        )


class CorreccionAnularFactura(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

        self.cliente = Cliente.objects.create(
            nombre="Cliente Test",
            correo="cliente@test.com",
            telefono="3001110000",
            direccion="Calle 1",
        )
        categoria = Categoria.objects.create(nombre="Cat Anular")
        self.producto = Product.objects.create(
            sku="SKU-AN1", nombre="Producto Anular", precio_venta=2000,
            categoria=categoria,
        )
        self.inventario = Inventory.objects.create(
            product=self.producto,
            branch=self.branch,
            cantidad_disponible=45,
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente, estado="pagado", total=10000
        )
        PedidoDetalle.objects.create(
            pedido=self.pedido, producto=self.producto,
            cantidad=5, precio_unitario=2000, subtotal=10000,
        )
        # La salida de kardex que deja confirmar_pagado: es la huella que
        # usa la devolucion para hallar la sucursal correcta.
        self.inventario.cantidad_disponible -= 5
        self.inventario.save(update_fields=["cantidad_disponible"])
        InventoryLog.objects.create(
            inventory=self.inventario,
            tipo_movimiento="SALIDA",
            cantidad=5,
            cantidad_resultante=40,
            motivo=_motivo_salida_confirmacion(self.pedido.id),
        )
        self.factura = Factura.objects.create(
            cliente=self.cliente,
            pedido=self.pedido,
            total=10000,
            estado="emitida",
        )

    def test_anular_factura_cancela_pedido_y_devuelve_stock(self):
        resp = self.client.post(
            reverse("effiadmi:anular_factura", args=[self.factura.id]), follow=True
        )
        self.factura.refresh_from_db()
        self.pedido.refresh_from_db()
        self.inventario.refresh_from_db()
        self.assertEqual(self.factura.estado, "anulada")
        self.assertEqual(self.pedido.estado, "cancelado")
        self.assertEqual(self.inventario.cantidad_disponible, 45)
        texto = " ".join(str(m) for m in resp.context["messages"])
        self.assertIn("anulada", texto)

        # Volver a anular no re-devuelve el stock dos veces (idempotente).
        self.client.post(reverse("effiadmi:anular_factura", args=[self.factura.id]))
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 45)

    def test_pedido_cancelable_despues_de_anular(self):
        self.client.post(reverse("effiadmi:anular_factura", args=[self.factura.id]))
        self.pedido.refresh_from_db()
        resp = self.client.post(
            reverse("effiadmi:cancelar_pedido", args=[self.pedido.id]), follow=True
        )
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, "cancelado")
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 45)

    def test_eliminar_factura_tambien_cancela_pedido(self):
        self.client.post(reverse("effiadmi:eliminar_factura", args=[self.factura.id]), follow=True)
        self.factura.refresh_from_db()
        self.pedido.refresh_from_db()
        self.inventario.refresh_from_db()
        self.assertEqual(self.factura.estado, "anulada")
        self.assertEqual(self.pedido.estado, "cancelado")
        self.assertEqual(self.inventario.cantidad_disponible, 45)


class CorreccionBusquedaPorId(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.cliente1 = Cliente.objects.create(
            nombre="Ana", correo="ana@mail.com",
            telefono="3001110000", direccion="Calle 1",
        )
        self.cliente2 = Cliente.objects.create(
            nombre="Carlos", correo="carlos@mail.com",
            telefono="3001110001", direccion="Calle 2",
        )
        self.pedido1 = Pedido.objects.create(cliente=self.cliente1, estado="pendiente", total=1)
        self.pedido2 = Pedido.objects.create(cliente=self.cliente2, estado="pendiente", total=2)

    def test_busqueda_pedidos_por_id_numerico(self):
        resp = self.client.get(reverse("effiadmi:lista_pedidos"), {"q": str(self.pedido2.id)})
        ids = [p.id for p in resp.context["pedidos"]]
        self.assertEqual(ids, [self.pedido2.id])

    def test_busqueda_pedidos_por_nombre(self):
        resp = self.client.get(reverse("effiadmi:lista_pedidos"), {"q": "Ana"})
        ids = [p.id for p in resp.context["pedidos"]]
        self.assertIn(self.pedido1.id, ids)
        self.assertNotIn(self.pedido2.id, ids)

    def test_busqueda_pedidos_por_id_sin_cero_resultados_ajenos(self):
        resp = self.client.get(reverse("effiadmi:lista_pedidos"), {"q": str(self.pedido1.id)})
        ids = [p.id for p in resp.context["pedidos"]]
        self.assertEqual(ids, [self.pedido1.id])


class CorreccionAjusteInventario(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.inventario = Inventory.objects.create(
            product=Product.objects.create(
                sku="SKU-AJ0", nombre="Producto Ajuste", precio_venta=100
            ),
            branch=self.branch,
            cantidad_disponible=8,
        )
        self.url = reverse("effiadmi:registrar_movimiento", args=[self.inventario.id])

    def test_ajuste_a_cero_valido(self):
        resp = self.client.post(self.url, {"tipo_movimiento": "AJUSTE", "cantidad": "0"}, follow=True)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 0)

    def test_ajuste_negativo_rechazado(self):
        self.client.post(self.url, {"tipo_movimiento": "AJUSTE", "cantidad": "-3"}, follow=True)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 8)

    def test_entrada_en_cero_rechazada(self):
        self.client.post(self.url, {"tipo_movimiento": "ENTRADA", "cantidad": "0"}, follow=True)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 8)

    def test_salida_en_cero_rechazada(self):
        self.client.post(self.url, {"tipo_movimiento": "SALIDA", "cantidad": "0"}, follow=True)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 8)


class ChatIaConMemoria(EffiBaseTestCase):
    """El historial de conversaciones se le pasa a la IA: sin esto, el
    asistente respondia cada pregunta como si fuera la primera y el hilo
    se perdia aunque los mensajes estuvieran guardados en la BD."""

    def setUp(self):
        super().setUp()
        from .models import ChatHistorial, Conversacion

        self.ChatHistorial = ChatHistorial
        self.Conversacion = Conversacion

    def test_responder_chat_envia_historial_previo(self):
        from unittest.mock import patch

        from .views import _responder_chat

        conv = self.Conversacion.objects.create(usuario=self.admin)
        self.ChatHistorial.objects.create(
            usuario=self.admin, conversacion=conv,
            mensaje="cuales proveedores surten cafe?", respuesta="El proveedor X surte cafe.",
        )

        with patch(
            "effiadmi.views.consultar_asistente_effiadmi",
            return_value="Respuesta normal",
        ) as mock_ia:
            _, respuesta = _responder_chat(self.admin, "y que mas surte?", conversacion=conv)

        self.assertEqual(respuesta, "Respuesta normal")
        historial = mock_ia.call_args.kwargs["historial"]
        self.assertEqual(historial, [("cuales proveedores surten cafe?", "El proveedor X surte cafe.")])

    def test_responder_chat_primer_mensaje_sin_historial(self):
        from unittest.mock import patch

        from .views import _responder_chat

        with patch(
            "effiadmi.views.consultar_asistente_effiadmi",
            return_value="Respuesta inicial",
        ) as mock_ia:
            conv, _ = _responder_chat(self.admin, "primera pregunta")

        historial = mock_ia.call_args.kwargs["historial"]
        self.assertEqual(historial, [])
        self.assertTrue(conv.mensajes.filter(mensaje="primera pregunta").exists())
