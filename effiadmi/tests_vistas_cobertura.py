"""Cobertura adicional de ramas de las vistas web.

Las pruebas existentes cubren los recorridos principales y la seguridad. Este
modulo agrega los caminos de error y los filtros que no se ejercitaban: campos
invalidos, estados de pedidos/facturas, filtros de los listados y el chat web.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .models import (
    Branch,
    Categoria,
    Cliente,
    Conversacion,
    CorreoEnviado,
    Factura,
    FacturaCompra,
    FacturaDetalle,
    Inventory,
    InventoryLog,
    Notificacion,
    Pedido,
    PedidoDetalle,
    Product,
    Proveedor,
    ProveedorProducto,
    Reporte,
)
from .soporte_pruebas import EffiBaseTestCase, textos_mensajes
from .views import _contexto_negocio_effiadmi, _es_error_ia, _titulo_conversacion


class ListadosYFiltrosTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.categoria = Categoria.objects.create(nombre="Bebidas")
        self.producto, self.inventario = self.crear_producto(
            nombre="Cafe molido", stock=2, stock_minimo=2
        )
        self.producto.categoria = self.categoria
        self.producto.save(update_fields=["categoria"])
        self.cliente = self.crear_cliente(nombre="Cliente Filtro", correo="filtro@test.com")
        self.proveedor = Proveedor.objects.create(
            nombre="Distribuidora Filtro",
            correo="proveedor-filtro@test.com",
            telefono="300",
            direccion="Calle",
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente, usuario=self.admin, total=Decimal("5000")
        )
        PedidoDetalle.objects.create(
            pedido=self.pedido,
            producto=self.producto,
            cantidad=1,
            precio_unitario=self.producto.precio_venta,
        )
        self.factura = Factura.objects.create(
            cliente=self.cliente, usuario=self.admin, pedido=self.pedido,
            total=Decimal("5000"),
        )
        FacturaDetalle.objects.create(
            factura=self.factura,
            producto=self.producto,
            cantidad=1,
            precio_unitario=self.producto.precio_venta,
        )
        self.notificacion = Notificacion.objects.create(
            usuario=self.admin, mensaje="Stock bajo de Cafe molido"
        )
        self.correo = CorreoEnviado.objects.create(
            usuario=self.admin,
            destinatario="destino@test.com",
            asunto="Asunto filtro",
            cuerpo="Cuerpo",
        )
        self.compra = FacturaCompra.objects.create(
            proveedor=self.proveedor,
            usuario=self.admin,
            numero="FC-FILTRO",
            fecha=date(2026, 10, 20),
            monto=Decimal("120000"),
        )

    def test_filtros_de_clientes_productos_categorias_e_inventario(self):
        self.assertEqual(
            self.client.get(reverse("effiadmi:lista_clientes"), {"q": "Filtro"}).context[
                "total_filtrados"
            ],
            1,
        )
        self.assertEqual(
            self.client.get(
                reverse("effiadmi:lista_productos"),
                {"q": "Cafe", "categoria": self.categoria.id},
            ).context["total_filtrados"],
            1,
        )
        self.producto.activo = False
        self.producto.save(update_fields=["activo"])
        self.assertEqual(
            self.client.get(
                reverse("effiadmi:lista_productos"), {"inactivos": "1"}
            ).context["total_filtrados"],
            1,
        )
        self.assertEqual(
            self.client.get(reverse("effiadmi:lista_categorias"), {"q": "Beb"}).context[
                "total_filtrados"
            ],
            1,
        )
        for parametros in (
            {"q": "Cafe"},
            {"sucursal": self.branch.id},
            {"categoria": self.categoria.id},
        ):
            with self.subTest(parametros=parametros):
                respuesta = self.client.get(reverse("effiadmi:lista_inventario"), parametros)
                self.assertEqual(respuesta.context["total_filtrados"], 1)

    def test_filtros_de_pedidos_facturas_usuarios_y_proveedores(self):
        self.assertEqual(
            self.client.get(reverse("effiadmi:lista_pedidos"), {"q": "Filtro"}).context[
                "total_filtrados"
            ],
            1,
        )
        self.assertEqual(
            self.client.get(
                reverse("effiadmi:lista_facturas"), {"q": "Filtro", "estado": "emitida"}
            ).context["total_filtrados"],
            1,
        )
        self.assertEqual(
            self.client.get(reverse("effiadmi:lista_usuarios"), {"q": "Oscar"}).context[
                "total_filtrados"
            ],
            1,
        )
        self.assertEqual(
            self.client.get(
                reverse("effiadmi:lista_proveedores"),
                {"q": "Filtro", "estado": "activo"},
            ).context["total_filtrados"],
            1,
        )

    def test_filtros_de_notificaciones_correos_y_compras(self):
        self.assertEqual(
            self.client.get(
                reverse("effiadmi:lista_notificaciones"), {"q": "Stock"}
            ).context["total_filtrados"],
            1,
        )
        self.assertEqual(
            self.client.get(reverse("effiadmi:lista_correos"), {"q": "destino"}).context[
                "total_filtrados"
            ],
            1,
        )
        self.assertEqual(
            self.client.get(
                reverse("effiadmi:lista_facturas_compra"),
                {"q": "FC-FILTRO", "mes": "2026-10", "proveedor": self.proveedor.id},
            ).context["total_filtrados"],
            1,
        )

    def test_dashboard_y_tabs_de_facturacion(self):
        respuesta = self.client.get(reverse("effiadmi:inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(self.inventario, respuesta.context["productos_bajo_stock"])

        respuesta = self.client.get(reverse("effiadmi:facturacion"), {"tab": "otro"})
        self.assertEqual(respuesta.context["tab"], "ventas")
        respuesta = self.client.get(
            reverse("effiadmi:facturacion"), {"tab": "compras", "mes": "2026-10"}
        )
        self.assertEqual(respuesta.context["tab"], "compras")

        self.iniciar_sesion(self.operador)
        respuesta = self.client.get(reverse("effiadmi:facturacion"), {"tab": "compras"})
        self.assertEqual(respuesta.context["tab"], "ventas")


class ProductosCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.categoria = Categoria.objects.create(nombre="Abarrotes")

    def _post_crear(self, **extra):
        datos = {
            "nombre": "Producto",
            "descripcion": "Descripcion",
            "categoria": self.categoria.id,
            "precio_venta": "5000",
            "sucursal": self.branch.id,
            "stock_inicial": "10",
            "stock_minimo": "2",
        }
        datos.update(extra)
        return self.client.post(reverse("effiadmi:crear_producto"), datos, follow=True)

    def test_crear_producto_rechaza_campos_invalidos(self):
        casos = [
            {"nombre": ""},
            {"categoria": ""},
            {"precio_venta": "abc"},
            {"precio_venta": "0"},
            {"precio_venta": "3000.50"},
            {"precio_venta": "500"},
            {"stock_inicial": "-1"},
            {"stock_minimo": "-1"},
        ]
        for extra in casos:
            with self.subTest(extra=extra):
                self._post_crear(**extra)
                self.assertFalse(
                    Product.objects.filter(nombre="Producto").exists(),
                    f"Se creo un producto con datos invalidos: {extra}",
                )

    def test_crear_producto_stock_invalido_usa_defaults(self):
        self._post_crear(stock_inicial="x", stock_minimo="y")
        producto = Product.objects.get(nombre="Producto")
        inventario = Inventory.objects.get(product=producto)
        self.assertEqual(inventario.cantidad_disponible, 0)
        self.assertEqual(inventario.stock_minimo, 5)
        self.assertFalse(InventoryLog.objects.filter(inventory=inventario).exists())

    def test_crear_producto_sin_sucursal_crea_la_principal(self):
        Branch.objects.all().delete()
        self._post_crear(sucursal=999999)
        self.assertTrue(Branch.objects.filter(es_principal=True).exists())
        self.assertTrue(Product.objects.filter(nombre="Producto").exists())

    def test_crear_producto_sku_duplicado_muestra_error(self):
        self.crear_producto(sku="1", nombre="Existente")
        with patch("effiadmi.views._siguiente_id_producto", return_value="1"):
            respuesta = self._post_crear(nombre="Duplicado")
        self.assertEqual(Product.objects.filter(sku="1").count(), 1)
        self.assertIn("SKU ya", " ".join(textos_mensajes(respuesta)))

    def test_editar_producto_valida_y_actualiza(self):
        producto, _ = self.crear_producto(sku="1", nombre="Original")
        url = reverse("effiadmi:editar_producto", args=[producto.id])
        datos = {
            "sku": "2",
            "nombre": "Editado",
            "descripcion": "Nueva",
            "precio_venta": "8000",
            "categoria": self.categoria.id,
        }
        for cambio in (
            {"sku": ""},
            {"sku": "ABC"},
            {"precio_venta": "x"},
            {"precio_venta": "0"},
            {"precio_venta": "1.5"},
            {"precio_venta": "500"},
            {"categoria": 999999},
        ):
            with self.subTest(cambio=cambio):
                respuesta = self.client.post(
                    url, {**datos, **cambio}, follow=True
                )
                producto.refresh_from_db()
                self.assertEqual(producto.nombre, "Original")
                self.assertEqual(respuesta.status_code, 200)

        respuesta = self.client.post(url, datos, follow=True)
        producto.refresh_from_db()
        self.assertEqual(producto.sku, "2")
        self.assertEqual(producto.nombre, "Editado")
        self.assertEqual(producto.precio_venta, Decimal("8000"))
        self.assertIn("actualizado", " ".join(textos_mensajes(respuesta)))

    def test_editar_producto_sin_categoria_la_deja_vacia(self):
        producto, _ = self.crear_producto(sku="1")
        self.client.post(
            reverse("effiadmi:editar_producto", args=[producto.id]),
            {"sku": "1", "nombre": "Sin categoria", "precio_venta": "5000", "categoria": ""},
            follow=True,
        )
        producto.refresh_from_db()
        self.assertIsNone(producto.categoria)

    def test_eliminar_producto_con_historial_y_reactivar(self):
        producto, _ = self.crear_producto(sku="1", stock=5)
        url = reverse("effiadmi:eliminar_producto", args=[producto.id])
        self.client.post(url, follow=True)
        producto.refresh_from_db()
        self.assertFalse(producto.activo)

        self.client.post(url, follow=True)
        producto.refresh_from_db()
        self.assertTrue(producto.activo)

    def test_eliminar_producto_sin_historial_lo_borra(self):
        producto = Product.objects.create(
            sku="99", nombre="Sin historial", precio_venta=5000, categoria=self.categoria
        )
        self.client.post(
            reverse("effiadmi:eliminar_producto", args=[producto.id]), follow=True
        )
        self.assertFalse(Product.objects.filter(id=producto.id).exists())


class CategoriasCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    def test_crear_categoria_vacia_duplicada_y_valida(self):
        self.client.post(reverse("effiadmi:crear_categoria"), {"nombre": "  "}, follow=True)
        self.assertFalse(Categoria.objects.exists())

        Categoria.objects.create(nombre="BEBIDAS")
        respuesta = self.client.post(
            reverse("effiadmi:crear_categoria"), {"nombre": "bebidas"}, follow=True
        )
        self.assertEqual(Categoria.objects.filter(nombre__iexact="bebidas").count(), 1)
        self.assertIn("ya existe", " ".join(textos_mensajes(respuesta)))

        respuesta = self.client.post(
            reverse("effiadmi:crear_categoria"), {"nombre": "aseo"}, follow=True
        )
        self.assertTrue(Categoria.objects.filter(nombre="ASEO").exists())
        self.assertIn("creada", " ".join(textos_mensajes(respuesta)))

    def test_editar_categoria_vacia_duplicada_y_valida(self):
        categoria = Categoria.objects.create(nombre="Bebidas")
        otra = Categoria.objects.create(nombre="Aseo")
        url = reverse("effiadmi:editar_categoria", args=[categoria.id])

        self.client.post(url, {"nombre": ""}, follow=True)
        self.client.post(url, {"nombre": "aseo"}, follow=True)
        categoria.refresh_from_db()
        self.assertEqual(categoria.nombre, "Bebidas")
        self.assertTrue(Categoria.objects.filter(id=otra.id).exists())

        respuesta = self.client.post(url, {"nombre": "Limpieza"}, follow=True)
        categoria.refresh_from_db()
        self.assertEqual(categoria.nombre, "LIMPIEZA")
        self.assertIn("actualizada", " ".join(textos_mensajes(respuesta)))

    def test_eliminar_categoria_con_productos_y_sin_productos(self):
        con_productos = Categoria.objects.create(nombre="Con productos")
        Product.objects.create(
            sku="1", nombre="Producto", precio_venta=5000, categoria=con_productos
        )
        self.client.post(
            reverse("effiadmi:eliminar_categoria", args=[con_productos.id]), follow=True
        )
        self.assertTrue(Categoria.objects.filter(id=con_productos.id).exists())

        vacia = Categoria.objects.create(nombre="Vacia")
        self.client.post(
            reverse("effiadmi:eliminar_categoria", args=[vacia.id]), follow=True
        )
        self.assertFalse(Categoria.objects.filter(id=vacia.id).exists())


class InventarioCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.operador)
        self.producto, self.inventario = self.crear_producto(stock=2, stock_minimo=2)

    def test_cantidad_no_numerica_no_cambia_el_stock(self):
        respuesta = self.client.post(
            reverse("effiadmi:registrar_movimiento", args=[self.inventario.id]),
            {"tipo_movimiento": "ENTRADA", "cantidad": "x"},
            follow=True,
        )
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 2)
        self.assertIn("no es valida", " ".join(textos_mensajes(respuesta)))

    def test_alerta_de_stock_bajo_no_duplica_la_notificacion(self):
        from .views import _notificar_stock_bajo

        _notificar_stock_bajo(self.inventario)
        _notificar_stock_bajo(self.inventario)
        self.assertEqual(
            Notificacion.objects.filter(mensaje__startswith="ALERTA: Stock bajo").count(),
            2,
        )


class PedidosCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.operador)
        self.producto, self.inventario = self.crear_producto(stock=10)
        self.cliente = self.crear_cliente()

    def _crear_pedido(self, estado="pendiente", con_detalle=True, inventario=True):
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            usuario=self.operador,
            estado=estado,
            total=Decimal("2000"),
        )
        if con_detalle:
            producto = self.producto
            if not inventario:
                producto = Product.objects.create(
                    sku="99", nombre="Sin inventario", precio_venta=2000
                )
            PedidoDetalle.objects.create(
                pedido=pedido,
                producto=producto,
                cantidad=1,
                precio_unitario=producto.precio_venta,
            )
        return pedido

    def test_crear_pedido_sin_cliente_y_sin_productos(self):
        respuesta = self.client.post(reverse("effiadmi:crear_pedido"), {}, follow=True)
        self.assertIn("seleccionar un cliente", " ".join(textos_mensajes(respuesta)))

        respuesta = self.client.post(
            reverse("effiadmi:crear_pedido"),
            {"cliente": self.cliente.id},
            follow=True,
        )
        self.assertIn("al menos un producto", " ".join(textos_mensajes(respuesta)))
        self.assertEqual(Pedido.objects.count(), 0)

    def test_crear_pedido_con_cantidad_invalida_no_deja_pedido(self):
        respuesta = self.client.post(
            reverse("effiadmi:crear_pedido"),
            {
                "cliente": self.cliente.id,
                "producto": [self.producto.id],
                "cantidad": ["0"],
            },
            follow=True,
        )
        self.assertIn("mayor a 0", " ".join(textos_mensajes(respuesta)))
        self.assertEqual(Pedido.objects.count(), 0)

    def test_confirmar_pedido_en_estado_incorrecto_sin_lineas_o_sin_inventario(self):
        pedido_confirmado = self._crear_pedido(estado="confirmado")
        respuesta = self.client.post(
            reverse("effiadmi:confirmar_pedido", args=[pedido_confirmado.id]),
            follow=True,
        )
        self.assertIn("pendientes", " ".join(textos_mensajes(respuesta)))

        pedido_vacio = self._crear_pedido(con_detalle=False)
        respuesta = self.client.post(
            reverse("effiadmi:confirmar_pedido", args=[pedido_vacio.id]), follow=True
        )
        self.assertIn("no tiene productos", " ".join(textos_mensajes(respuesta)))

        pedido_sin_inventario = self._crear_pedido(inventario=False)
        respuesta = self.client.post(
            reverse("effiadmi:confirmar_pedido", args=[pedido_sin_inventario.id]),
            follow=True,
        )
        self.assertIn("No hay inventario", " ".join(textos_mensajes(respuesta)))

    def test_confirmar_pedido_sin_sucursales(self):
        pedido = self._crear_pedido()
        Branch.objects.all().delete()
        respuesta = self.client.post(
            reverse("effiadmi:confirmar_pedido", args=[pedido.id]), follow=True
        )
        self.assertIn("No hay sucursales", " ".join(textos_mensajes(respuesta)))

    def test_cancelar_cancelado_y_pendiente_no_devuelve_stock(self):
        cancelado = self._crear_pedido(estado="cancelado")
        respuesta = self.client.post(
            reverse("effiadmi:cancelar_pedido", args=[cancelado.id]), follow=True
        )
        self.assertIn("ya esta cancelado", " ".join(textos_mensajes(respuesta)))

        pendiente = self._crear_pedido()
        self.client.post(
            reverse("effiadmi:cancelar_pedido", args=[pendiente.id]), follow=True
        )
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 10)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, "cancelado")

    def test_cancelar_confirmado_sin_kardex_devuelve_a_la_principal(self):
        pedido = self._crear_pedido(estado="confirmado")
        self.client.post(
            reverse("effiadmi:cancelar_pedido", args=[pedido.id]), follow=True
        )
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad_disponible, 11)

    def test_pagar_pedido_no_confirmado_o_ya_facturado(self):
        pendiente = self._crear_pedido()
        respuesta = self.client.post(
            reverse("effiadmi:pagar_pedido", args=[pendiente.id]), follow=True
        )
        self.assertIn("confirmados", " ".join(textos_mensajes(respuesta)))

        confirmado = self._crear_pedido(estado="confirmado")
        Factura.objects.create(
            cliente=self.cliente, usuario=self.operador, pedido=confirmado,
            total=confirmado.total, estado="emitida",
        )
        respuesta = self.client.post(
            reverse("effiadmi:pagar_pedido", args=[confirmado.id]), follow=True
        )
        self.assertIn("ya tiene una factura", " ".join(textos_mensajes(respuesta)))

    def test_eliminar_pedido_no_pendiente(self):
        pedido = self._crear_pedido(estado="confirmado")
        self.iniciar_sesion(self.admin)
        respuesta = self.client.post(
            reverse("effiadmi:eliminar_pedido", args=[pedido.id]), follow=True
        )
        self.assertTrue(Pedido.objects.filter(id=pedido.id).exists())
        self.assertIn("pendientes", " ".join(textos_mensajes(respuesta)))


class FacturasCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.cliente = self.crear_cliente()
        self.producto, _ = self.crear_producto()

    def _factura(self, estado="emitida"):
        return Factura.objects.create(
            cliente=self.cliente,
            usuario=self.admin,
            total=Decimal("5000"),
            estado=estado,
        )

    def test_anular_factura_get_ya_anulada_y_emitida(self):
        emitida = self._factura()
        url = reverse("effiadmi:anular_factura", args=[emitida.id])
        self.assertEqual(self.client.get(url).status_code, 302)
        emitida.refresh_from_db()
        self.assertEqual(emitida.estado, "emitida")

        self.client.post(url, follow=True)
        emitida.refresh_from_db()
        self.assertEqual(emitida.estado, "anulada")

        respuesta = self.client.post(url, follow=True)
        self.assertIn("ya esta anulada", " ".join(textos_mensajes(respuesta)))

    def test_eliminar_factura_emitida_y_ya_anulada(self):
        factura = self._factura()
        url = reverse("effiadmi:eliminar_factura", args=[factura.id])
        self.client.post(url, follow=True)
        factura.refresh_from_db()
        self.assertEqual(factura.estado, "anulada")

        respuesta = self.client.post(url, follow=True)
        self.assertIn("ya esta anulada", " ".join(textos_mensajes(respuesta)))


class UsuariosCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    def test_crear_usuario_campos_faltantes_y_duplicado(self):
        respuesta = self.client.post(reverse("effiadmi:crear_usuario"), {}, follow=True)
        self.assertIn("completa todos", " ".join(textos_mensajes(respuesta)))

        respuesta = self.client.post(
            reverse("effiadmi:crear_usuario"),
            {"nombre_usuario": "Dup", "email": self.admin.email, "contraseña": "ClaveRobusta2026!"},
            follow=True,
        )
        self.assertIn("ya esta registrado", " ".join(textos_mensajes(respuesta)))

    def test_editar_usuario_correo_invalido_y_exito(self):
        url = reverse("effiadmi:editar_usuario", args=[self.operador.id])
        respuesta = self.client.post(
            url,
            {
                "nombre_usuario": "Oscar",
                "apellido_usuario": "Oper",
                "email": "correo-invalido",
                "cargo": "operador",
            },
            follow=True,
        )
        self.operador.refresh_from_db()
        self.assertEqual(self.operador.email, "oper@test.com")
        self.assertIn("símbolo '@'", " ".join(textos_mensajes(respuesta)))

        respuesta = self.client.post(
            url,
            {
                "nombre_usuario": "Oscar Editado",
                "apellido_usuario": "Oper",
                "email": "oper-editado@test.com",
                "cargo": "admin",
                "contraseña": "OtraClaveSegura2026!",
            },
            follow=True,
        )
        self.operador.refresh_from_db()
        self.operador.profile.refresh_from_db()
        self.assertEqual(self.operador.first_name, "Oscar Editado")
        self.assertEqual(self.operador.profile.cargo, "admin")
        self.assertTrue(self.operador.check_password("OtraClaveSegura2026!"))
        self.assertIn("actualizado", " ".join(textos_mensajes(respuesta)))

    def test_activar_usuario_inactivo(self):
        self.operador.is_active = False
        self.operador.save(update_fields=["is_active"])
        self.client.post(
            reverse("effiadmi:eliminar_usuario", args=[self.operador.id]), follow=True
        )
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.is_active)

    def test_perfil_invalido_y_actualizacion_valida(self):
        self.iniciar_sesion(self.operador)
        url = reverse("effiadmi:perfil")
        respuesta = self.client.post(url, {"email": "mal"}, follow=True)
        self.assertIn("símbolo '@'", " ".join(textos_mensajes(respuesta)))

        respuesta = self.client.post(
            url,
            {
                "email": "oper-nuevo@test.com",
                "nombre": "Oscar Nuevo",
                "apellido": "Oper",
                "telefono": "3001234567",
                "direccion": "Calle 2",
            },
            follow=True,
        )
        self.operador.refresh_from_db()
        self.operador.profile.refresh_from_db()
        self.assertEqual(self.operador.email, "oper-nuevo@test.com")
        self.assertEqual(self.operador.profile.direccion, "Calle 2")
        self.assertEqual(self.client.session["logueado"]["nombre"], "Oscar Nuevo")
        self.assertIn("actualizado", " ".join(textos_mensajes(respuesta)))


class ProveedoresCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.proveedor = Proveedor.objects.create(
            nombre="Proveedor", correo="proveedor@test.com", telefono="1", direccion="Calle"
        )
        self.producto, _ = self.crear_producto()

    def test_crear_proveedor_campos_faltantes(self):
        respuesta = self.client.post(
            reverse("effiadmi:crear_proveedor"), {"nombre_proveedor": "Incompleto"},
            follow=True,
        )
        self.assertIn("completa todos", " ".join(textos_mensajes(respuesta)))
        self.assertFalse(Proveedor.objects.filter(nombre="Incompleto").exists())

    def test_editar_proveedor_correo_invalido_y_valido(self):
        url = reverse("effiadmi:editar_proveedor", args=[self.proveedor.id])
        respuesta = self.client.post(
            url,
            {"nombre_proveedor": "X", "correo": "mal", "telefono": "3001234567", "direccion": "x"},
            follow=True,
        )
        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.nombre, "Proveedor")
        self.assertIn("símbolo '@'", " ".join(textos_mensajes(respuesta)))

        respuesta = self.client.post(
            url,
            {
                "nombre_proveedor": "Proveedor Editado",
                "correo": "proveedor-editado@test.com",
                "telefono": "3001234567",
                "direccion": "Otra",
            },
            follow=True,
        )
        self.proveedor.refresh_from_db()
        self.assertEqual(self.proveedor.nombre, "Proveedor Editado")
        self.assertIn("actualizado", " ".join(textos_mensajes(respuesta)))

    def test_eliminar_proveedor_inactivo_lo_activa(self):
        self.proveedor.activo = False
        self.proveedor.save(update_fields=["activo"])
        self.client.post(
            reverse("effiadmi:eliminar_proveedor", args=[self.proveedor.id]), follow=True
        )
        self.proveedor.refresh_from_db()
        self.assertTrue(self.proveedor.activo)

    def test_detalle_agregar_y_quitar_producto(self):
        url_detalle = reverse("effiadmi:detalle_proveedor", args=[self.proveedor.id])
        self.assertEqual(self.client.get(url_detalle).status_code, 200)

        url_agregar = reverse(
            "effiadmi:agregar_producto_proveedor", args=[self.proveedor.id]
        )
        respuesta = self.client.post(
            url_agregar, {"producto": 999999, "precio_compra": "1000"}, follow=True
        )
        self.assertIn("producto y un precio", " ".join(textos_mensajes(respuesta)))

        self.client.post(
            url_agregar,
            {"producto": self.producto.id, "precio_compra": "3000"},
            follow=True,
        )
        relacion = ProveedorProducto.objects.get(
            proveedor=self.proveedor, producto=self.producto
        )
        self.client.post(
            reverse(
                "effiadmi:eliminar_producto_proveedor",
                args=[self.proveedor.id, relacion.id],
            ),
            follow=True,
        )
        self.assertFalse(
            ProveedorProducto.objects.filter(id=relacion.id).exists()
        )


class NotificacionesCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.notificacion = Notificacion.objects.create(
            usuario=self.admin, mensaje="Notificacion de prueba"
        )

    def test_detalle_marca_como_leida_y_elimina(self):
        self.client.get(
            reverse("effiadmi:detalle_notificacion", args=[self.notificacion.id])
        )
        self.notificacion.refresh_from_db()
        self.assertTrue(self.notificacion.leido)

        self.client.post(
            reverse("effiadmi:eliminar_notificacion", args=[self.notificacion.id]),
            follow=True,
        )
        self.assertFalse(Notificacion.objects.filter(id=self.notificacion.id).exists())


class AuthYRecuperacionCoberturaTest(EffiBaseTestCase):
    def test_login_campos_vacios_y_correo_invalido(self):
        url = reverse("effiadmi:login")
        respuesta = self.client.post(url, {}, follow=True)
        self.assertIn("Escribe tu correo", " ".join(textos_mensajes(respuesta)))

        respuesta = self.client.post(
            url, {"username": "mal", "password": "x"}, follow=True
        )
        self.assertIn("símbolo '@'", " ".join(textos_mensajes(respuesta)))

    def test_login_get_con_sesion_redirige_al_inicio(self):
        self.iniciar_sesion(self.operador)
        respuesta = self.client.get(reverse("effiadmi:login"))
        self.assertRedirects(respuesta, reverse("effiadmi:inicio"))

    def test_logout_elimina_la_sesion(self):
        self.iniciar_sesion(self.operador)
        self.client.get(reverse("effiadmi:logout"), follow=True)
        self.assertNotIn("logueado", self.client.session)

    def test_solicitar_recuperacion_vacio_bloqueado_y_valido(self):
        url = reverse("effiadmi:solicitar_recuperacion")
        respuesta = self.client.post(url, {"email": ""})
        self.assertIn("error", respuesta.context)

        respuesta = self.client.post(url, {"email": self.operador.email})
        self.assertTrue(respuesta.context["enviado"])
        respuesta = self.client.post(url, {"email": self.operador.email})
        self.assertTrue(respuesta.context["enviado"])

    def test_restablecer_password_corta_debil_y_valida(self):
        from .views import token_recuperacion

        token = token_recuperacion(self.operador)
        url = reverse("effiadmi:restablecer_password", args=[token])
        respuesta = self.client.post(
            url, {"password": "corta", "password_confirm": "corta"}
        )
        self.assertIn("error", respuesta.context)

        respuesta = self.client.post(
            url, {"password": "12345678", "password_confirm": "12345678"}
        )
        self.assertIn("error", respuesta.context)

        respuesta = self.client.post(
            url,
            {
                "password": "NuevaClaveSegura2026!",
                "password_confirm": "NuevaClaveSegura2026!",
            },
            follow=True,
        )
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.check_password("NuevaClaveSegura2026!"))
        self.assertIn("actualizada", " ".join(textos_mensajes(respuesta)))

    def test_restablecer_password_token_invalido(self):
        respuesta = self.client.get(
            reverse("effiadmi:restablecer_password", args=["token-invalido"])
        )
        self.assertFalse(respuesta.context["valido"])


class IaWebCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)

    @patch("effiadmi.views.consultar_asistente_effiadmi", return_value="Respuesta **ok**")
    def test_post_crea_conversacion_y_redirige(self, _mock):
        respuesta = self.client.post(
            reverse("effiadmi:estadisticas_ia"), {"pregunta": "Como va el inventario?"}
        )
        conversacion = Conversacion.objects.get(usuario=self.admin)
        self.assertEqual(conversacion.titulo, "Como va el inventario?")
        self.assertIn(f"conversacion={conversacion.id}", respuesta["Location"])
        self.assertTrue(conversacion.mensajes.exists())

    @patch("effiadmi.views.consultar_asistente_effiadmi", return_value="Respuesta **ok**")
    def test_ajax_ok_devuelve_html(self, _mock):
        respuesta = self.client.post(
            reverse("effiadmi:estadisticas_ia"),
            {"pregunta": "Hola"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["ok"])
        self.assertIn("<strong>ok</strong>", respuesta.json()["respuesta_html"])

    def test_ajax_vacio_nueva_y_limite(self):
        respuesta = self.client.post(
            reverse("effiadmi:estadisticas_ia"),
            {"pregunta": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertFalse(respuesta.json()["ok"])

        respuesta = self.client.post(
            reverse("effiadmi:estadisticas_ia"),
            {"nueva_conversacion": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertTrue(respuesta.json()["nueva"])

        with patch("effiadmi.views.limite_alcanzado", return_value=True):
            respuesta = self.client.post(
                reverse("effiadmi:estadisticas_ia"),
                {"pregunta": "Hola"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertFalse(respuesta.json()["ok"])

    @patch("effiadmi.views.consultar_asistente_effiadmi", return_value="Error: fallo")
    def test_error_ia_ajax_no_deja_conversacion(self, _mock):
        respuesta = self.client.post(
            reverse("effiadmi:estadisticas_ia"),
            {"pregunta": "Hola"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertFalse(respuesta.json()["ok"])
        self.assertFalse(Conversacion.objects.filter(usuario=self.admin).exists())

    def test_historial_invalido_y_eliminar_conversacion(self):
        respuesta = self.client.get(reverse("effiadmi:estadisticas_ia"), {"hist": "x"})
        self.assertEqual(respuesta.context["hist_limite"], 8)

        respuesta = self.client.post(
            reverse("effiadmi:eliminar_conversacion", args=[999999]), follow=True
        )
        self.assertIn("no encontrada", " ".join(textos_mensajes(respuesta)))

        conversacion = Conversacion.objects.create(usuario=self.admin)
        url = reverse("effiadmi:eliminar_conversacion", args=[conversacion.id])
        self.client.get(url, follow=True)
        self.assertTrue(Conversacion.objects.filter(id=conversacion.id).exists())
        self.client.post(url, follow=True)
        self.assertFalse(Conversacion.objects.filter(id=conversacion.id).exists())

    def test_contexto_negocio_y_utilidades_chat(self):
        self.crear_producto(stock=1, stock_minimo=2)
        contexto = _contexto_negocio_effiadmi()
        self.assertEqual(contexto["Productos activos"], 1)
        self.assertIn("Productos bajo stock", contexto)
        self.assertTrue(_es_error_ia(""))
        self.assertTrue(_es_error_ia("No hay clave de Gemini"))
        self.assertFalse(_es_error_ia("respuesta"))
        self.assertTrue(_titulo_conversacion("x" * 70).endswith("…"))
        self.assertEqual(_titulo_conversacion(""), "Historial")


class ReportesCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.reporte = Reporte.objects.create(
            usuario=self.operador,
            titulo="Reporte de stock",
            descripcion="Falta producto",
        )

    def test_listado_admin_con_filtros_y_operador(self):
        self.iniciar_sesion(self.admin)
        respuesta = self.client.get(
            reverse("effiadmi:reportes"), {"q": "stock", "estado": "pendiente"}
        )
        self.assertEqual(respuesta.context["total_filtrados"], 1)

        self.iniciar_sesion(self.operador)
        respuesta = self.client.get(reverse("effiadmi:reportes"), {"q": "Falta"})
        self.assertEqual(respuesta.context["total_filtrados"], 1)

    def test_crear_reporte_incompleto_y_valido(self):
        self.iniciar_sesion(self.operador)
        respuesta = self.client.post(
            reverse("effiadmi:reportes"), {"titulo": "Solo titulo"}, follow=True
        )
        self.assertIn("titulo y la descripcion", " ".join(textos_mensajes(respuesta)))

        respuesta = self.client.post(
            reverse("effiadmi:reportes"),
            {"titulo": "Nuevo", "descripcion": "Detalle", "tipo": "reporte_stock"},
            follow=True,
        )
        self.assertTrue(Reporte.objects.filter(titulo="Nuevo").exists())
        self.assertIn("enviado", " ".join(textos_mensajes(respuesta)))

    def test_detalle_operador_ajeno_y_admin_responde(self):
        self.iniciar_sesion(self.operador)
        ajeno = Reporte.objects.create(
            usuario=self.admin, titulo="Ajeno", descripcion="No debe verlo"
        )
        respuesta = self.client.get(
            reverse("effiadmi:detalle_reporte", args=[ajeno.id]), follow=True
        )
        self.assertIn("No tienes acceso", " ".join(textos_mensajes(respuesta)))

        self.iniciar_sesion(self.admin)
        respuesta = self.client.get(
            reverse("effiadmi:detalle_reporte", args=[self.reporte.id])
        )
        self.reporte.refresh_from_db()
        self.assertEqual(self.reporte.estado, "visto")
        self.assertEqual(respuesta.status_code, 200)

        respuesta = self.client.post(
            reverse("effiadmi:detalle_reporte", args=[self.reporte.id]),
            {"respuesta": "Resuelto por admin", "estado": "resuelto"},
            follow=True,
        )
        self.reporte.refresh_from_db()
        self.assertEqual(self.reporte.estado, "resuelto")
        self.assertEqual(self.reporte.respuesta, "Resuelto por admin")
        self.assertIn("actualizado", " ".join(textos_mensajes(respuesta)))


class CorreosCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.iniciar_sesion(self.admin)

    def _post(self, **extra):
        datos = {
            "destinatario": "cliente@test.com",
            "asunto": "Asunto",
            "cuerpo": "Mensaje",
        }
        datos.update(extra)
        return self.client.post(reverse("effiadmi:lista_correos"), datos, follow=True)

    def test_listado_operador_solo_ve_sus_correos(self):
        CorreoEnviado.objects.create(
            usuario=self.admin, destinatario="admin@test.com", asunto="Admin", cuerpo="x"
        )
        CorreoEnviado.objects.create(
            usuario=self.operador, destinatario="oper@test.com", asunto="Oper", cuerpo="x"
        )
        self.iniciar_sesion(self.operador)
        respuesta = self.client.get(reverse("effiadmi:lista_correos"))
        self.assertEqual(respuesta.context["total_filtrados"], 1)

    def test_validaciones_del_formulario(self):
        respuesta = self._post(destinatario="")
        self.assertIn("Completa", " ".join(textos_mensajes(respuesta)))
        respuesta = self._post(asunto="x" * 201)
        self.assertIn("200 caracteres", " ".join(textos_mensajes(respuesta)))
        respuesta = self._post(destinatario="mal")
        self.assertIn("símbolo '@'", " ".join(textos_mensajes(respuesta)))

    def test_limite_de_envios(self):
        with patch("effiadmi.views.limite_alcanzado", return_value=True):
            respuesta = self._post()
        self.assertIn("muchos correos", " ".join(textos_mensajes(respuesta)))
        self.assertFalse(CorreoEnviado.objects.exists())

    @patch("effiadmi.views.enviar_correo", return_value=(True, ""))
    def test_envio_exitoso_y_fallido(self, _mock):
        self._post()
        correo = CorreoEnviado.objects.get()
        self.assertTrue(correo.exitoso)

        with patch("effiadmi.views.enviar_correo", return_value=(False, "sin SMTP")):
            respuesta = self._post(destinatario="otro@test.com")
        self.assertEqual(CorreoEnviado.objects.count(), 2)
        self.assertIn("No se pudo enviar", " ".join(textos_mensajes(respuesta)))


class FacturasCompraCoberturaTest(EffiBaseTestCase):
    def setUp(self):
        super().setUp()
        self.iniciar_sesion(self.admin)
        self.proveedor = Proveedor.objects.create(
            nombre="Proveedor Compra",
            correo="compra@test.com",
            telefono="1",
            direccion="Calle",
        )

    def _post(self, **extra):
        datos = {
            "proveedor": self.proveedor.id,
            "numero": "FC-100",
            "fecha": "2026-10-20",
            "monto": "100000",
            "notas": "Compra",
        }
        datos.update(extra)
        return self.client.post(
            reverse("effiadmi:crear_factura_compra"), datos, follow=True
        )

    def test_validaciones_de_fecha_monto_y_adjunto(self):
        respuesta = self._post(fecha="")
        self.assertIn("fecha es obligatoria", " ".join(textos_mensajes(respuesta)))

        respuesta = self._post(fecha="20-10-2026")
        self.assertIn("fecha no es valida", " ".join(textos_mensajes(respuesta)))

        respuesta = self._post(monto="x")
        self.assertIn("monto no es valido", " ".join(textos_mensajes(respuesta)))

        respuesta = self._post(monto="-1")
        self.assertIn("no puede ser negativo", " ".join(textos_mensajes(respuesta)))

        archivo = SimpleUploadedFile("factura.txt", b"contenido", content_type="text/plain")
        respuesta = self._post(archivo=archivo)
        self.assertIn("no permitido", " ".join(textos_mensajes(respuesta)))
        self.assertEqual(FacturaCompra.objects.count(), 0)

    def test_crear_factura_compra_valida(self):
        respuesta = self._post(notas="")
        self.assertEqual(FacturaCompra.objects.count(), 1)
        factura = FacturaCompra.objects.get()
        self.assertEqual(factura.numero, "FC-100")
        self.assertEqual(factura.monto, Decimal("100000"))
        self.assertIn("registrada", " ".join(textos_mensajes(respuesta)))
