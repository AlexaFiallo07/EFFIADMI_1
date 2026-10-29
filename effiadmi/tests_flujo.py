"""Prueba de integracion del flujo de negocio completo via HTTP.

Producto -> Pedido -> Confirmacion (descuenta stock) -> Factura -> Pago, mas
cancelacion y revertido de stock. Es el recorrido que un operador/admin hace en
la app real, ejercitando las vistas y la BD a la vez.
"""

from django.urls import reverse

from .models import (
    Categoria,
    Cliente,
    Factura,
    Inventory,
    InventoryLog,
    Notificacion,
    Pedido,
    Product,
)
from .soporte_pruebas import EffiBaseTestCase


class FlujoNegocioTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.categoria = Categoria.objects.create(nombre="Bebidas")

    def _crear_producto(self, stock=10):
        self.client.post(
            reverse("effiadmi:crear_producto"),
            {
                "nombre": "Gaseosa",
                "descripcion": "1.5L",
                "categoria": self.categoria.id,
                "precio_venta": "5000",
                "sucursal": self.branch.id,
                "stock_inicial": str(stock),
                "stock_minimo": "2",
            },
            follow=True,
        )
        return Product.objects.get(nombre="Gaseosa")

    def _crear_cliente(self):
        self.client.post(
            reverse("effiadmi:crear_cliente"),
            {"nombre": "Flujo", "correo": "flujo@test.com", "telefono": "3001234567", "direccion": "Calle"},
            follow=True,
        )
        return Cliente.objects.get(correo="flujo@test.com")

    def test_flujo_completo_hasta_la_factura(self):
        producto = self._crear_producto(stock=10)
        cliente = self._crear_cliente()

        self.client.post(
            reverse("effiadmi:crear_pedido"),
            {"cliente": cliente.id, "producto": [producto.id], "cantidad": ["3"]},
            follow=True,
        )
        pedido = Pedido.objects.latest("id")
        self.assertEqual(pedido.estado, "pendiente")
        self.assertEqual(pedido.total, producto.precio_venta * 3)

        self.client.post(reverse("effiadmi:confirmar_pedido", args=[pedido.id]), follow=True)
        self.client.post(reverse("effiadmi:pagar_pedido", args=[pedido.id]), follow=True)

        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "pagado")

        inventario = Inventory.objects.get(product=producto, branch=self.branch)
        self.assertEqual(inventario.cantidad_disponible, 7)

        factura = Factura.objects.get(pedido=pedido)
        self.assertEqual(factura.estado, "emitida")
        self.assertEqual(factura.total, producto.precio_venta * 3)
        self.assertEqual(factura.detalles.count(), 1)
        self.assertEqual(factura.detalles.first().producto, producto)

        self.assertGreaterEqual(Notificacion.objects.filter(usuario=self.admin).count(), 2)

    def test_cancelar_pedido_confirmado_devuelve_stock(self):
        producto = self._crear_producto(stock=10)
        cliente = self._crear_cliente()

        self.client.post(
            reverse("effiadmi:crear_pedido"),
            {"cliente": cliente.id, "producto": [producto.id], "cantidad": ["4"]},
            follow=True,
        )
        pedido = Pedido.objects.latest("id")
        self.client.post(reverse("effiadmi:confirmar_pedido", args=[pedido.id]), follow=True)

        inventario = Inventory.objects.get(product=producto, branch=self.branch)
        self.assertEqual(inventario.cantidad_disponible, 6)

        self.client.post(reverse("effiadmi:cancelar_pedido", args=[pedido.id]), follow=True)
        pedido.refresh_from_db()
        inventario.refresh_from_db()
        self.assertEqual(pedido.estado, "cancelado")
        self.assertEqual(inventario.cantidad_disponible, 10)
        self.assertTrue(
            InventoryLog.objects.filter(
                inventory=inventario, motivo__icontains="Devolucion"
            ).exists()
        )

    def test_no_se_puede_cancelar_un_pedido_pagado(self):
        producto = self._crear_producto(stock=10)
        cliente = self._crear_cliente()

        self.client.post(
            reverse("effiadmi:crear_pedido"),
            {"cliente": cliente.id, "producto": [producto.id], "cantidad": ["2"]},
            follow=True,
        )
        pedido = Pedido.objects.latest("id")
        self.client.post(reverse("effiadmi:confirmar_pedido", args=[pedido.id]), follow=True)
        self.client.post(reverse("effiadmi:pagar_pedido", args=[pedido.id]), follow=True)

        self.client.post(reverse("effiadmi:cancelar_pedido", args=[pedido.id]), follow=True)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "pagado")

    def test_movimiento_que_deja_stock_bajo_notifica(self):
        producto, inventario = self.crear_producto(stock=3, stock_minimo=2)
        self.iniciar_sesion(self.operador)
        antes = Notificacion.objects.count()

        self.client.post(
            reverse("effiadmi:registrar_movimiento", args=[inventario.id]),
            {"tipo_movimiento": "SALIDA", "cantidad": "1", "motivo": "venta"},
            follow=True,
        )

        inventario.refresh_from_db()
        self.assertEqual(inventario.cantidad_disponible, 2)
        self.assertGreater(Notificacion.objects.count(), antes)
