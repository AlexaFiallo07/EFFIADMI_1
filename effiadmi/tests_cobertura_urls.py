"""Barrido integral de todas las rutas del sitio.

El escenario de la defensa es un profesor tocando la aplicacion a mano, asi
que aqui se recorre cada URL nombrada del proyecto con objetos reales en la
BD y en tres estados de sesion. Invariantes exigidos:

* Con sesion (admin y operador): toda ruta termina en una pagina renderizada
  (200), sin excepciones, sin plantillas rotas y sin que la aplicacion rebote
  al login.
* Sin sesion: ninguna ruta muestra contenido (302 a login o 404).

Ademas se comprueba que el barrido cubra exactamente el conjunto de rutas que
existen en los urlconf: si alguien anade una URL nueva y no la cubre, este
test avisa en lugar de dejar un hueco silencioso.
"""

from datetime import date

import logging

from django.urls import URLPattern, URLResolver, get_resolver, reverse

from landing.views import MODULOS

from .models import (
    ChatHistorial,
    Cliente,
    Conversacion,
    CorreoEnviado,
    Factura,
    FacturaCompra,
    FacturaDetalle,
    Notificacion,
    Pedido,
    PedidoDetalle,
    Product,
    Proveedor,
    ProveedorProducto,
    Reporte,
)
from .soporte_pruebas import EffiBaseTestCase
from .views import token_recuperacion

# Rutas publicas: se pueden abrir sin sesion y deben responder.
RUTAS_PUBLICAS = {"login", "logout", "solicitar_recuperacion", "restablecer_password"}

# Rutas que no llevan argumentos de tipo <int:id> / <str:token>.
RUTAS_SIN_ARGUMENTOS = [
    "inicio",
    "perfil",
    "lista_clientes",
    "crear_cliente",
    "lista_productos",
    "crear_producto",
    "lista_categorias",
    "crear_categoria",
    "lista_inventario",
    "facturacion",
    "lista_facturas",
    "lista_pedidos",
    "crear_pedido",
    "lista_usuarios",
    "crear_usuario",
    "lista_proveedores",
    "crear_proveedor",
    "lista_notificaciones",
    "estadisticas_ia",
    "reportes",
    "lista_correos",
    "lista_facturas_compra",
    "crear_factura_compra",
    "exportar_facturas_compra_excel",
    "login",
    "solicitar_recuperacion",
]

# Rutas con argumentos: nombre -> tupla de ids (se rellenan en setUp).
RUTAS_CON_ARGUMENTOS = (
    "editar_cliente",
    "eliminar_cliente",
    "editar_producto",
    "eliminar_producto",
    "editar_categoria",
    "eliminar_categoria",
    "detalle_inventario",
    "registrar_movimiento",
    "detalle_factura",
    "editar_factura",
    "anular_factura",
    "eliminar_factura",
    "detalle_pedido",
    "confirmar_pedido",
    "cancelar_pedido",
    "pagar_pedido",
    "editar_pedido",
    "eliminar_pedido",
    "editar_usuario",
    "eliminar_usuario",
    "detalle_proveedor",
    "editar_proveedor",
    "eliminar_proveedor",
    "agregar_producto_proveedor",
    "eliminar_producto_proveedor",
    "detalle_notificacion",
    "eliminar_notificacion",
    "detalle_reporte",
    "eliminar_conversacion",
    "restablecer_password",
)

RUTAS_LANDING = [
    "landing",
    "solucion",
    "modulos",
    "proceso",
    "tecnologia",
    "contacto",
]


def _nombres_ruteados():
    """Nombres de las rutas de la app y del landing (sin admin ni API)."""
    nombres = set()
    for patron in get_resolver().url_patterns:
        if not isinstance(patron, URLResolver):
            continue
        if getattr(patron, "urlconf_name", None) not in ("effiadmi.urls", "landing.urls"):
            continue
        for hijo in patron.url_patterns:
            if isinstance(hijo, URLPattern) and hijo.name:
                nombres.add(hijo.name)
    return nombres


class _CapturaDeErrores(logging.Handler):
    """Guarda los registros ERROR emitidos durante el barrido.

    Varias vistas envuelven su cuerpo en `try/except` y, ante una excepcion,
    registran el traceback y devuelven una pagina de error con estado 200. Sin
    esta captura el barrido daria por buena una pagina que en realidad fallo
    (asi se detecto el bug de la exportacion a Excel).
    """

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.registros = []

    def emit(self, record):
        self.registros.append(record)

    def resumen(self):
        return "\n".join(
            f"{registro.name}: {registro.getMessage()}" for registro in self.registros
        )


class BarridoSitioTest(EffiBaseTestCase):
    """Recorre cada URL del proyecto en los tres estados de sesion."""

    def setUp(self):
        super().setUp()
        self.cliente = self.crear_cliente()
        self.producto, self.inventario = self.crear_producto()
        self.categoria = self.producto.categoria
        self.proveedor = Proveedor.objects.create(
            nombre="Distribuidora Norte",
            correo="norte@test.com",
            telefono="3009998877",
            direccion="Carrera 7 #8-9",
        )
        self.relacion = ProveedorProducto.objects.create(
            proveedor=self.proveedor,
            producto=self.producto,
            precio_compra=3000,
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente,
            usuario=self.admin,
            total=self.producto.precio_venta * 2,
        )
        PedidoDetalle.objects.create(
            pedido=self.pedido,
            producto=self.producto,
            cantidad=2,
            precio_unitario=self.producto.precio_venta,
            subtotal=self.producto.precio_venta * 2,
        )
        self.factura = Factura.objects.create(
            cliente=self.cliente,
            usuario=self.admin,
            pedido=self.pedido,
            total=self.producto.precio_venta * 2,
        )
        FacturaDetalle.objects.create(
            factura=self.factura,
            producto=self.producto,
            cantidad=2,
            precio_unitario=self.producto.precio_venta,
            subtotal=self.producto.precio_venta * 2,
        )
        self.notificacion_admin = Notificacion.objects.create(
            usuario=self.admin,
            mensaje="Stock bajo del producto Cafe molido",
        )
        self.notificacion_operador = Notificacion.objects.create(
            usuario=self.operador,
            mensaje="Pedido confirmado",
        )
        self.reporte = Reporte.objects.create(
            usuario=self.admin,
            titulo="Falta insumo",
            descripcion="Revisar proveedor de empaques",
        )
        self.conversacion = Conversacion.objects.create(
            usuario=self.admin,
            titulo="Consulta de margen",
        )
        ChatHistorial.objects.create(
            usuario=self.admin,
            conversacion=self.conversacion,
            mensaje="Cual es el margen del cafe?",
            respuesta="El margen del cafe es del 40%.",
        )
        CorreoEnviado.objects.create(
            usuario=self.admin,
            destinatario="cliente1@test.com",
            asunto="Bienvenida",
            cuerpo="Gracias por tu compra.",
        )
        FacturaCompra.objects.create(
            proveedor=self.proveedor,
            usuario=self.admin,
            numero="FC-0001",
            fecha=date.today(),
            monto=150000,
        )
        self.token = token_recuperacion(self.admin)

    def _argumentos(self, nombre, usuario):
        """Ids reales para cada ruta que los pide.

        Las notificaciones son por usuario (IDOR: el operador no debe poder
        ver la del admin), asi que cada rol recorre la suya propia.
        """
        notificacion = usuario.notificaciones.first() or self.notificacion_admin
        ids = {
            "editar_cliente": (self.cliente.id,),
            "eliminar_cliente": (self.cliente.id,),
            "editar_producto": (self.producto.id,),
            "eliminar_producto": (self.producto.id,),
            "editar_categoria": (self.categoria.id,),
            "eliminar_categoria": (self.categoria.id,),
            "detalle_inventario": (self.inventario.id,),
            "registrar_movimiento": (self.inventario.id,),
            "detalle_factura": (self.factura.id,),
            "editar_factura": (self.factura.id,),
            "anular_factura": (self.factura.id,),
            "eliminar_factura": (self.factura.id,),
            "detalle_pedido": (self.pedido.id,),
            "confirmar_pedido": (self.pedido.id,),
            "cancelar_pedido": (self.pedido.id,),
            "pagar_pedido": (self.pedido.id,),
            "editar_pedido": (self.pedido.id,),
            "eliminar_pedido": (self.pedido.id,),
            "editar_usuario": (self.operador.id,),
            "eliminar_usuario": (self.operador.id,),
            "detalle_proveedor": (self.proveedor.id,),
            "editar_proveedor": (self.proveedor.id,),
            "eliminar_proveedor": (self.proveedor.id,),
            "agregar_producto_proveedor": (self.proveedor.id,),
            "eliminar_producto_proveedor": (self.proveedor.id, self.relacion.id),
            "detalle_notificacion": (notificacion.id,),
            "eliminar_notificacion": (notificacion.id,),
            "detalle_reporte": (self.reporte.id,),
            "eliminar_conversacion": (self.conversacion.id,),
            "restablecer_password": (self.token,),
        }
        return ids[nombre]

    def _recorridas(self, usuario):
        """(nombre, args, metodo) de toda la app, sin logout (romperia la sesion).

        Las vistas que solo actuan por POST (marcar_todas_leidas) se piden con
        POST: un GET ya no cambia estado.
        """
        for nombre in RUTAS_SIN_ARGUMENTOS:
            metodo = "post" if nombre == "marcar_todas_leidas" else "get"
            yield nombre, (), metodo
        for nombre in RUTAS_CON_ARGUMENTOS:
            yield nombre, self._argumentos(nombre, usuario), "get"

    def _recorrer_con_sesion(self, usuario):
        self.iniciar_sesion(usuario)
        login_url = reverse("effiadmi:login")
        recorridas = list(self._recorridas(usuario))
        self.assertTrue(recorridas)

        captura = _CapturaDeErrores()
        afectados = [logging.getLogger("effiadmi"), logging.getLogger("django.request")]
        for logger in afectados:
            logger.addHandler(captura)
        try:
            for nombre, args, metodo in recorridas:
                with self.subTest(url=nombre, usuario=usuario.username):
                    cliente = getattr(self.client, metodo)
                    respuesta = cliente(
                        reverse(f"effiadmi:{nombre}", args=args), follow=True
                    )
                    self.assertEqual(
                        respuesta.status_code,
                        200,
                        f"{nombre} no termino en una pagina renderizada "
                        f"(cadena: {respuesta.redirect_chain})",
                    )
                    for destino, codigo in respuesta.redirect_chain:
                        self.assertIn(codigo, (301, 302, 303, 307, 308))
                        self.assertFalse(
                            destino.startswith(login_url),
                            f"{nombre} reboto al login con la sesion iniciada",
                        )
        finally:
            for logger in afectados:
                logger.removeHandler(captura)

        self.assertEqual(
            captura.registros,
            [],
            "Errores registrados durante el barrido (fueron tragados por la "
            f"vista y devolvieron 200 igual):\n{captura.resumen()}",
        )

    def test_admin_recorre_toda_la_aplicacion_sin_errores(self):
        """Ninguna pagina falla para el rol con todos los permisos."""
        self._recorrer_con_sesion(self.admin)

    def test_operador_recorre_toda_la_aplicacion_sin_errores(self):
        """Tampoco para un rol limitado (lo redirigen, pero nunca truena)."""
        self._recorrer_con_sesion(self.operador)

    def test_sin_sesion_no_muestra_contenido(self):
        """Cualquier ruta protegida devuelve 302 a login o 404, nunca 200."""
        self.client.logout()
        for nombre, args, _metodo in self._recorridas(self.admin):
            if nombre in RUTAS_PUBLICAS:
                continue
            with self.subTest(url=nombre):
                respuesta = self.client.get(
                    reverse(f"effiadmi:{nombre}", args=args)
                )
                self.assertIn(
                    respuesta.status_code,
                    (302, 404),
                    f"{nombre} es accesible sin sesion",
                )

    def test_landing_publica_responde(self):
        """Las paginas de venta se ven sin sesion."""
        rutas = [reverse(nombre) for nombre in RUTAS_LANDING]
        rutas += [reverse("modulo", args=[m["slug"]]) for m in MODULOS]
        for ruta in rutas:
            with self.subTest(url=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200, ruta)

    def test_logout_cierra_la_sesion(self):
        self.iniciar_sesion(self.admin)
        respuesta = self.client.get(reverse("effiadmi:logout"), follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(self.client.session.get("logueado"))

    def test_el_barrido_cubre_todas_las_rutas_definidas(self):
        """Si aparece una URL nueva, este test exige que entre al barrido."""
        descubiertas = _nombres_ruteados()
        cubiertas = set(RUTAS_SIN_ARGUMENTOS) | set(RUTAS_CON_ARGUMENTOS)
        cubiertas |= RUTAS_PUBLICAS
        cubiertas |= set(RUTAS_LANDING) | {"logout", "modulo"}

        faltan = descubiertas - cubiertas
        self.assertEqual(
            faltan,
            set(),
            f"Rutas sin cubrir en el barrido: {sorted(faltan)}",
        )

    def test_marcar_todas_leidas_solo_por_post(self):
        """Un GET no debe cambiar estado (evita CSRF por <img>)."""
        self.iniciar_sesion(self.admin)
        self.notificacion_admin.leido = False
        self.notificacion_admin.save(update_fields=["leido"])
        self.client.get(reverse("effiadmi:marcar_todas_leidas"), follow=True)
        self.notificacion_admin.refresh_from_db()
        self.assertFalse(self.notificacion_admin.leido)
        self.client.post(reverse("effiadmi:marcar_todas_leidas"), follow=True)
        self.notificacion_admin.refresh_from_db()
        self.assertTrue(self.notificacion_admin.leido)
