"""Pruebas de modelos: validaciones, subtotales y restricciones de BD."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from .models import (
    Branch,
    Categoria,
    Cliente,
    Factura,
    FacturaDetalle,
    Inventory,
    InventoryLog,
    Pedido,
    PedidoDetalle,
    Product,
    Proveedor,
    ProveedorProducto,
    UserProfile,
)
from .soporte_pruebas import EffiBaseTestCase


class ProductoModeloTest(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Bebidas")

    def test_producto_valido_pasa_full_clean(self):
        producto = Product(sku="100", nombre="Agua", precio_venta=Decimal("2500.00"), categoria=self.categoria)
        producto.full_clean()  # no debe lanzar

    def test_sku_no_numerico_falla(self):
        producto = Product(sku="ABC-1", nombre="Agua", precio_venta=Decimal("2500"), categoria=self.categoria)
        with self.assertRaises(ValidationError) as ctx:
            producto.full_clean()
        self.assertIn("sku", ctx.exception.message_dict)

    def test_precio_cero_falla(self):
        producto = Product(sku="101", nombre="Agua", precio_venta=Decimal("0"), categoria=self.categoria)
        with self.assertRaises(ValidationError) as ctx:
            producto.full_clean()
        self.assertIn("precio_venta", ctx.exception.message_dict)

    def test_precio_negativo_falla(self):
        producto = Product(sku="102", nombre="Agua", precio_venta=Decimal("-1"), categoria=self.categoria)
        with self.assertRaises(ValidationError) as ctx:
            producto.full_clean()
        self.assertIn("precio_venta", ctx.exception.message_dict)

    def test_str_incluye_sku_y_nombre(self):
        producto = Product.objects.create(sku="103", nombre="Agua", precio_venta=Decimal("2500"), categoria=self.categoria)
        self.assertEqual(str(producto), "[103] Agua")

    def test_sku_es_unico(self):
        Product.objects.create(sku="104", nombre="A", precio_venta=Decimal("1"))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(sku="104", nombre="B", precio_venta=Decimal("1"))

    def test_categoria_con_productos_no_se_puede_borrar(self):
        Product.objects.create(sku="105", nombre="A", precio_venta=Decimal("1"), categoria=self.categoria)
        with self.assertRaises(ProtectedError):
            self.categoria.delete()


class CategoriaModeloTest(TestCase):
    def test_nombre_unico(self):
        Categoria.objects.create(nombre="Snacks")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Categoria.objects.create(nombre="Snacks")


class ClienteModeloTest(TestCase):
    def test_correo_unico(self):
        Cliente.objects.create(nombre="A", correo="a@test.com", telefono="1", direccion="x")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Cliente.objects.create(nombre="B", correo="a@test.com", telefono="1", direccion="x")

    def test_activo_por_defecto(self):
        cliente = Cliente.objects.create(nombre="A", correo="a@test.com", telefono="1", direccion="x")
        self.assertTrue(cliente.activo)


class InventarioModeloTest(EffiBaseTestCase):
    def test_no_puede_repetir_producto_y_sucursal(self):
        producto, _ = self.crear_producto()
        otra = Branch.objects.create(nombre="Sucursal 2")
        Inventory.objects.create(product=producto, branch=otra, cantidad_disponible=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Inventory.objects.create(product=producto, branch=otra, cantidad_disponible=1)

    def test_inventorylog_str(self):
        _, inventario = self.crear_producto()
        log = InventoryLog.objects.create(
            inventory=inventario,
            tipo_movimiento=InventoryLog.ENTRADA,
            cantidad=5,
            cantidad_resultante=15,
        )
        self.assertIn("ENTRADA x5", str(log))


class DetalleSubtotalTest(EffiBaseTestCase):
    def test_pedido_detalle_calcula_subtotal_al_guardar(self):
        producto, _ = self.crear_producto()
        cliente = self.crear_cliente()
        pedido = Pedido.objects.create(cliente=cliente)
        detalle = PedidoDetalle.objects.create(
            pedido=pedido,
            producto=producto,
            cantidad=3,
            precio_unitario=Decimal("2000.00"),
            subtotal=Decimal("0"),
        )
        self.assertEqual(detalle.subtotal, Decimal("6000.00"))

    def test_factura_detalle_calcula_subtotal_al_guardar(self):
        producto, _ = self.crear_producto()
        cliente = self.crear_cliente()
        factura = Factura.objects.create(cliente=cliente)
        detalle = FacturaDetalle.objects.create(
            factura=factura,
            producto=producto,
            cantidad=2,
            precio_unitario=Decimal("3500.00"),
            subtotal=Decimal("0"),
        )
        self.assertEqual(detalle.subtotal, Decimal("7000.00"))

    def test_pedido_por_defecto_pendiente_y_total_cero(self):
        pedido = Pedido.objects.create(cliente=self.crear_cliente())
        self.assertEqual(pedido.estado, "pendiente")
        self.assertEqual(pedido.total, Decimal("0"))


class VariosModeloTest(EffiBaseTestCase):
    def test_userprofile_str_muestra_cargo(self):
        self.assertIn("admin", str(self.admin.profile))

    def test_proveedor_producto_str(self):
        proveedor = Proveedor.objects.create(nombre="Prov", correo="p@test.com", telefono="1", direccion="x")
        producto, _ = self.crear_producto()
        relacion = ProveedorProducto.objects.create(proveedor=proveedor, producto=producto, precio_compra=Decimal("100"))
        self.assertEqual(str(relacion), "Prov -> Cafe molido")

    def test_branch_str(self):
        self.assertEqual(str(self.branch), "Sucursal Principal")

    def test_errores_clean_no_se_mezclan(self):
        producto = Product(sku="XX", nombre="N", precio_venta=Decimal("0"))
        with self.assertRaises(ValidationError) as ctx:
            producto.full_clean()
        self.assertEqual(set(ctx.exception.message_dict), {"sku", "precio_venta"})
