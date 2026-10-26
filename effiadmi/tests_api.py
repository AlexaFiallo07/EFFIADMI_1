"""Pruebas de la API REST: autenticacion, permisos, paginacion, throttling, IA."""

from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import (
    Branch,
    Categoria,
    Cliente,
    Inventory,
    InventoryLog,
    Notificacion,
    Product,
    UserProfile,
)


class ApiBaseTestCase(APITestCase):
    def setUp(self):
        cache.clear()  # reinicia los contadores de throttling
        self.admin = self._usuario("admin@api.test", "admin")
        self.operador = self._usuario("oper@api.test", "operador")
        self.branch = Branch.objects.create(nombre="Principal", es_principal=True)

    @staticmethod
    def _usuario(email, cargo):
        user = User.objects.create_user(username=email, email=email, password="ClaveSegura123!")
        UserProfile.objects.create(user=user, cargo=cargo)
        return user

    def autenticar(self, user=None):
        self.client.force_authenticate(user=user or self.admin)

    def crear_inventario(self, cantidad=10, stock_minimo=2):
        categoria = Categoria.objects.create(nombre="General")
        producto = Product.objects.create(sku="1", nombre="Cafe", precio_venta=5000, categoria=categoria)
        inventario = Inventory.objects.create(
            product=producto, branch=self.branch,
            cantidad_disponible=cantidad, stock_minimo=stock_minimo,
        )
        return producto, inventario


class PerimetrosTest(ApiBaseTestCase):
    def test_sin_autenticacion_devuelve_401(self):
        respuesta = self.client.get("/api/catalogo-productos/")
        self.assertEqual(respuesta.status_code, 401)

    def test_catalogos_protegidos_uno_por_uno(self):
        for url in (
            "/api/sucursales/", "/api/stock/", "/api/clientes/",
            "/api/proveedores/", "/api/facturas/", "/api/pedidos/",
            "/api/notificaciones/", "/api/dashboard/estadisticas/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)


class ProductosApiTest(ApiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.autenticar()

    def test_lista_paginada(self):
        categoria = Categoria.objects.create(nombre="General")
        for i in range(25):
            Product.objects.create(sku=str(i + 1), nombre=f"P{i}", precio_venta=1000, categoria=categoria)
        respuesta = self.client.get("/api/catalogo-productos/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["count"], 25)
        self.assertEqual(len(respuesta.data["results"]), 20)
        self.assertIsNotNone(respuesta.data["next"])

    def test_crear_producto_genera_inventario_y_kardex(self):
        respuesta = self.client.post(
            "/api/catalogo-productos/",
            {
                "sku": "1", "nombre": "Arroz", "precio_venta": "5000",
                "sucursal_id": self.branch.id, "stock_inicial": 7, "stock_minimo_inicial": 2,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        producto = Product.objects.get(sku="1")
        inventario = Inventory.objects.get(product=producto, branch=self.branch)
        self.assertEqual(inventario.cantidad_disponible, 7)
        self.assertTrue(InventoryLog.objects.filter(inventory=inventario, tipo_movimiento="ENTRADA").exists())

    def test_sku_no_numerico_da_400(self):
        respuesta = self.client.post(
            "/api/catalogo-productos/",
            {"sku": "ABC", "nombre": "X", "precio_venta": "5000"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("sku", respuesta.data)

    def test_precio_cero_da_400(self):
        respuesta = self.client.post(
            "/api/catalogo-productos/",
            {"sku": "2", "nombre": "X", "precio_venta": "0"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("precio_venta", respuesta.data)

    def test_sucursal_inexistente_da_400(self):
        respuesta = self.client.post(
            "/api/catalogo-productos/",
            {"sku": "3", "nombre": "X", "precio_venta": "5000", "sucursal_id": 9999},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)


class StockApiTest(ApiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.autenticar(self.operador)
        self.producto, self.inventario = self.crear_inventario(cantidad=10)

    def _ajustar(self, tipo, cantidad):
        return self.client.post(
            "/api/stock/ajustar-stock/",
            {"product_id": self.producto.id, "sucursal_id": self.branch.id,
             "tipo_movimiento": tipo, "cantidad": cantidad},
            format="json",
        )

    def test_entrada_aumenta_stock(self):
        respuesta = self._ajustar("ENTRADA", 5)
        self.assertEqual(respuesta.status_code, 200)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 15)
        self.assertFalse(respuesta.data["alerta_reabastecimiento"])

    def test_salida_insuficiente_da_400(self):
        respuesta = self._ajustar("SALIDA", 100)
        self.assertEqual(respuesta.status_code, 400)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 10)

    def test_cantidad_cero_da_400(self):
        self.assertEqual(self._ajustar("ENTRADA", 0).status_code, 400)

    def test_inventario_inexistente_da_404(self):
        respuesta = self.client.post(
            "/api/stock/ajustar-stock/",
            {"product_id": 9999, "sucursal_id": self.branch.id, "tipo_movimiento": "ENTRADA", "cantidad": 1},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_kardex_filtra_por_producto(self):
        self._ajustar("ENTRADA", 5)
        respuesta = self.client.get(f"/api/stock/kardex/?product_id={self.producto.id}")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data), 1)

    def test_cantidad_disponible_es_solo_lectura(self):
        # Ajustar el campo directo esta restringido a admin (permission_classes);
        # el operador cambia stock solo por la accion ajustar-stock.
        respuesta = self.client.patch(
            f"/api/stock/{self.inventario.id}/", {"cantidad_disponible": 999}, format="json"
        )
        self.assertEqual(respuesta.status_code, 403)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 10)


class ClientesApiTest(ApiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.autenticar(self.operador)

    def test_crear_cliente(self):
        respuesta = self.client.post(
            "/api/clientes/",
            {"nombre": "Cli", "correo": "c@api.test", "telefono": "1", "direccion": "x"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(Cliente.objects.filter(correo="c@api.test").exists())

    def test_correo_duplicado_da_400(self):
        Cliente.objects.create(nombre="A", correo="dup@api.test", telefono="1", direccion="x")
        respuesta = self.client.post(
            "/api/clientes/",
            {"nombre": "B", "correo": "dup@api.test", "telefono": "1", "direccion": "x"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)


class NotificacionesApiTest(ApiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.notif_admin = Notificacion.objects.create(usuario=self.admin, mensaje="para admin")
        self.notif_oper = Notificacion.objects.create(usuario=self.operador, mensaje="para oper")

    def test_solo_ve_las_suyas(self):
        self.autenticar(self.admin)
        respuesta = self.client.get("/api/notificaciones/")
        ids = [n["id"] for n in respuesta.data["results"]]
        self.assertEqual(ids, [self.notif_admin.id])

    def test_no_puede_leer_la_de_otro(self):
        self.autenticar(self.admin)
        respuesta = self.client.get(f"/api/notificaciones/{self.notif_oper.id}/")
        self.assertEqual(respuesta.status_code, 404)

    def test_marca_como_leida_la_propia(self):
        self.autenticar(self.admin)
        respuesta = self.client.patch(
            f"/api/notificaciones/{self.notif_admin.id}/", {"leido": True}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200)
        self.notif_admin.refresh_from_db()
        self.assertTrue(self.notif_admin.leido)

    def test_no_se_puede_crear_por_api(self):
        self.autenticar(self.admin)
        respuesta = self.client.post("/api/notificaciones/", {"mensaje": "falsa"}, format="json")
        self.assertEqual(respuesta.status_code, 405)


class FacturasPedidosApiTest(ApiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.autenticar()
        self.cliente = Cliente.objects.create(nombre="Cli", correo="c@api.test", telefono="1", direccion="x")
        self.producto, _ = self.crear_inventario()

    def _linea(self):
        return {"producto": self.producto.id, "cantidad": 1, "precio_unitario": "5000"}

    def test_factura_asigna_usuario_emisor(self):
        respuesta = self.client.post(
            "/api/facturas/",
            {"cliente": self.cliente.id, "detalles": [self._linea()]},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        from .models import Factura

        self.assertEqual(Factura.objects.get(id=respuesta.data["id"]).usuario, self.admin)

    def test_pedido_no_permite_mass_assignment_de_estado(self):
        respuesta = self.client.post(
            "/api/pedidos/",
            {"cliente": self.cliente.id, "estado": "pagado", "detalles": [self._linea()]},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        from .models import Pedido

        self.assertEqual(Pedido.objects.get(id=respuesta.data["id"]).estado, "pendiente")


class DashboardApiTest(ApiBaseTestCase):
    def test_estadisticas_trae_estructura(self):
        self.autenticar()
        respuesta = self.client.get("/api/dashboard/estadisticas/")
        self.assertEqual(respuesta.status_code, 200)
        for clave in ("totales", "inventario", "movimientos", "ventas_por_producto", "reposicion_sugerida"):
            self.assertIn(clave, respuesta.data)


class AsistenteIaApiTest(ApiBaseTestCase):
    URL = "/api/ia/consultar/"

    def setUp(self):
        super().setUp()
        self.autenticar()

    def test_mensaje_vacio_da_400(self):
        self.assertEqual(self.client.post(self.URL, {}, format="json").status_code, 400)

    def test_mensaje_muy_largo_da_400(self):
        respuesta = self.client.post(self.URL, {"mensaje": "x" * 2001}, format="json")
        self.assertEqual(respuesta.status_code, 400)

    @patch("effiadmi.api_views.consultar_asistente_effiadmi", return_value="Respuesta simulada")
    def test_respuesta_ok_con_ia_mockeada(self, _mock):
        respuesta = self.client.post(self.URL, {"mensaje": "hola"}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["respuesta"], "Respuesta simulada")

    @patch("effiadmi.api_views.consultar_asistente_effiadmi", return_value="ok")
    def test_throttle_de_ia_limita(self, _mock):
        limite = int(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["ia"].split("/")[0])
        for _ in range(limite):
            self.assertEqual(self.client.post(self.URL, {"mensaje": "hola"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(self.URL, {"mensaje": "hola"}, format="json").status_code, 429)


class EscaladaDePrivilegiosApiTest(ApiBaseTestCase):
    """Un operador no debe poder hacer por API lo que la web reserva a admin."""

    def setUp(self):
        super().setUp()
        self.cliente_obj = Cliente.objects.create(
            nombre="Cli", correo="c@api.test", telefono="1", direccion="x"
        )
        from .models import Factura, Pedido

        self.factura = Factura.objects.create(
            cliente=self.cliente_obj, usuario=self.admin, total=1000
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente_obj, usuario=self.admin, total=1000
        )

    def test_operador_no_borra_facturas(self):
        self.autenticar(self.operador)
        self.assertEqual(
            self.client.delete(f"/api/facturas/{self.factura.id}/").status_code, 403
        )
        from .models import Factura

        self.assertTrue(Factura.objects.filter(id=self.factura.id).exists())

    def test_operador_no_crea_productos(self):
        self.autenticar(self.operador)
        respuesta = self.client.post(
            "/api/catalogo-productos/",
            {"sku": "9", "nombre": "Hack", "precio_venta": "9999"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_operador_no_borra_sucursales(self):
        self.autenticar(self.operador)
        self.assertEqual(
            self.client.delete(f"/api/sucursales/{self.branch.id}/").status_code, 403
        )

    def test_operador_no_borra_pedidos(self):
        self.autenticar(self.operador)
        self.assertEqual(
            self.client.delete(f"/api/pedidos/{self.pedido.id}/").status_code, 403
        )

    def test_operador_puede_leer_catalogos(self):
        self.autenticar(self.operador)
        self.assertEqual(self.client.get("/api/catalogo-productos/").status_code, 200)

    def test_admin_si_borra_facturas(self):
        self.autenticar(self.admin)
        from .models import Factura

        respuesta = self.client.delete(f"/api/facturas/{self.factura.id}/")
        self.assertEqual(respuesta.status_code, 204)
        self.assertFalse(Factura.objects.filter(id=self.factura.id).exists())


class TokenApiTest(ApiBaseTestCase):
    def test_token_con_credenciales_validas(self):
        respuesta = self.client.post(
            "/api/token/",
            {"username": self.admin.email, "password": "ClaveSegura123!"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("access", respuesta.data)

    def test_token_con_clave_incorrecta_da_401(self):
        respuesta = self.client.post(
            "/api/token/",
            {"username": self.admin.email, "password": "mala"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 401)


class BackendAutenticacionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="juan", email="juan@test.com", password="ClaveSegura123!"
        )

    def test_autentica_por_usuario(self):
        from django.contrib.auth import authenticate

        self.assertEqual(authenticate(username="juan", password="ClaveSegura123!"), self.user)

    def test_autentica_por_email(self):
        from django.contrib.auth import authenticate

        self.assertEqual(authenticate(username="juan@test.com", password="ClaveSegura123!"), self.user)

    def test_clave_incorrecta_devuelve_none(self):
        from django.contrib.auth import authenticate

        self.assertIsNone(authenticate(username="juan@test.com", password="mala"))

    def test_usuario_inactivo_no_autentica(self):
        from django.contrib.auth import authenticate

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertIsNone(authenticate(username="juan@test.com", password="ClaveSegura123!"))
