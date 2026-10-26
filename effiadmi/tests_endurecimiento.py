"""Regresion de los hallazgos de la auditoria de seguridad.

Cubre: /media/ con validacion de propiedad, cuentas desactivadas en la API,
borrado protegido de documentos fiscales, throttle que contaba logins
exitosos y creacion de facturas/pedidos con sus lineas (antes quedaban vacios).
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import (
    Cliente,
    Categoria,
    Factura,
    FacturaDetalle,
    Pedido,
    Product,
    RegistroIngreso,
    UserProfile,
)
from .soporte_pruebas import EffiBaseTestCase

User = get_user_model()


class UsuarioInactivoApiTest(APITestCase):
    """Un token ya emitido deja de servir cuando la cuenta se desactiva."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="inactivo@test.com",
            email="inactivo@test.com",
            password="ClaveSegura123!",
        )
        UserProfile.objects.create(user=self.user, cargo="operador")

    def test_token_de_usuario_desactivado_da_401(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        token = str(RefreshToken.for_user(self.user).access_token)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        respuesta = self.client.get("/api/catalogo-productos/")
        self.assertEqual(respuesta.status_code, 401)

    def test_backend_get_user_ignora_inactivos(self):
        from .views import EmailOrUsernameBackend

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertIsNone(EmailOrUsernameBackend().get_user(self.user.pk))


class ThrottleLoginExitosoTest(EffiBaseTestCase):
    """Los logins correctos no deben consumir el limite por IP."""

    def test_login_exitoso_libera_el_contador_de_ip(self):
        url = reverse("effiadmi:login")
        for _ in range(12):
            respuesta = self.client.post(
                url,
                {"username": self.operador.email, "password": self.CLAVE},
            )
            self.assertNotEqual(respuesta.status_code, 429)
        self.assertIsNone(cache.get("throttle:login:127.0.0.1"))


class BorradoProtegidoApiTest(APITestCase):
    """Borrar un cliente o producto con documentos asociados da 409, no 500."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username="admin@protect.test",
            email="admin@protect.test",
            password="ClaveSegura123!",
        )
        UserProfile.objects.create(user=self.admin, cargo="admin")
        self.client.force_authenticate(user=self.admin)

        self.cliente = Cliente.objects.create(
            nombre="Cli", correo="cli@protect.test", telefono="1", direccion="x"
        )
        self.producto = Product.objects.create(
            sku="1",
            nombre="Cafe",
            precio_venta=1000,
            categoria=Categoria.objects.create(nombre="General"),
        )
        self.factura = Factura.objects.create(
            cliente=self.cliente, usuario=self.admin, total=1000
        )
        FacturaDetalle.objects.create(
            factura=self.factura,
            producto=self.producto,
            cantidad=1,
            precio_unitario=1000,
        )

    def test_no_borra_cliente_con_facturas(self):
        respuesta = self.client.delete(f"/api/clientes/{self.cliente.id}/")
        self.assertEqual(respuesta.status_code, 409)
        self.assertTrue(Cliente.objects.filter(id=self.cliente.id).exists())

    def test_no_borra_producto_con_facturas(self):
        respuesta = self.client.delete(f"/api/catalogo-productos/{self.producto.id}/")
        self.assertEqual(respuesta.status_code, 409)
        self.assertTrue(Product.objects.filter(id=self.producto.id).exists())

    def test_registro_ingreso_sobrevive_al_usuario(self):
        registro = RegistroIngreso.objects.create(usuario=self.admin, rol="admin")
        self.admin.delete()
        registro.refresh_from_db()
        self.assertIsNone(registro.usuario)
        self.assertIn("usuario eliminado", str(registro))


class DocumentosApiTest(APITestCase):
    """POST de facturas/pedidos exige lineas y calcula el total."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username="admin@doc.test",
            email="admin@doc.test",
            password="ClaveSegura123!",
        )
        UserProfile.objects.create(user=self.admin, cargo="admin")
        self.operador = User.objects.create_user(
            username="oper@doc.test",
            email="oper@doc.test",
            password="ClaveSegura123!",
        )
        UserProfile.objects.create(user=self.operador, cargo="operador")
        self.client.force_authenticate(user=self.admin)

        self.cliente = Cliente.objects.create(
            nombre="Cli", correo="cli@doc.test", telefono="1", direccion="x"
        )
        self.producto = Product.objects.create(
            sku="1",
            nombre="Cafe",
            precio_venta=1500,
            categoria=Categoria.objects.create(nombre="General"),
        )

    def _linea(self, cantidad=2, precio="1500"):
        return {
            "producto": self.producto.id,
            "cantidad": cantidad,
            "precio_unitario": precio,
        }

    def test_factura_con_lineas_calcula_total_y_expone_estado(self):
        respuesta = self.client.post(
            "/api/facturas/",
            {"cliente": self.cliente.id, "detalles": [self._linea()]},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(Decimal(respuesta.data["total"]), Decimal("3000.00"))
        self.assertEqual(respuesta.data["estado"], "emitida")
        self.assertEqual(
            FacturaDetalle.objects.filter(factura_id=respuesta.data["id"]).count(), 1
        )

    def test_factura_sin_lineas_da_400(self):
        respuesta = self.client.post(
            "/api/facturas/", {"cliente": self.cliente.id}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("detalles", respuesta.data)

    def test_pedido_con_lineas_calcula_total(self):
        respuesta = self.client.post(
            "/api/pedidos/",
            {"cliente": self.cliente.id, "detalles": [self._linea(cantidad=3)]},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(Decimal(respuesta.data["total"]), Decimal("4500.00"))

    def test_pedido_sin_lineas_da_400(self):
        respuesta = self.client.post(
            "/api/pedidos/", {"cliente": self.cliente.id}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_operador_no_reasigna_el_cliente_de_un_pedido(self):
        pedido = Pedido.objects.create(
            cliente=self.cliente, usuario=self.admin, total=0
        )
        otro = Cliente.objects.create(
            nombre="Otro", correo="otro@doc.test", telefono="2", direccion="y"
        )
        self.client.force_authenticate(user=self.operador)
        respuesta = self.client.patch(
            f"/api/pedidos/{pedido.id}/", {"cliente": otro.id}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400)
        pedido.refresh_from_db()
        self.assertEqual(pedido.cliente_id, self.cliente.id)
