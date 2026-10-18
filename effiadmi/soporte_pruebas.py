"""Utilidades compartidas por los modulos de pruebas de `effiadmi`.

No es un modulo de tests (el descubridor de Django solo carga los archivos
`test*.py`), asi que aqui vive la base comun sin que se ejecute como suite.
"""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from .models import Branch, Categoria, Cliente, Inventory, Product, UserProfile


def textos_mensajes(respuesta):
    """Devuelve los mensajes flash de una respuesta sin romper si no hay."""
    try:
        return [str(m) for m in respuesta.context["messages"]]
    except (AttributeError, KeyError, TypeError):
        return []


class EffiBaseTestCase(TestCase):
    """Crea dos usuarios (admin/operador), una sucursal y limpia la cache.

    La cache limpia en `setUp` es clave: el limitador de login por IP y el
    candado de 5 fallos viven en la cache y, al ser locmem compartida entre
    casos, sin esto un test bloquearia a los siguientes.
    """

    CLAVE = "ClaveSegura123!"

    def setUp(self):
        cache.clear()
        self.admin = self.crear_usuario("admin@test.com", "Ana", "Admin", "admin")
        self.operador = self.crear_usuario("oper@test.com", "Oscar", "Oper", "operador")
        self.branch = Branch.objects.create(
            nombre="Sucursal Principal",
            direccion="Calle 1 #2-3",
            es_principal=True,
        )

    @staticmethod
    def crear_usuario(email, nombre, apellido, cargo, activo=True):
        user = User.objects.create_user(
            username=email,
            email=email,
            password="ClaveSegura123!",
            first_name=nombre,
            last_name=apellido,
        )
        if not activo:
            user.is_active = False
            user.save(update_fields=["is_active"])
        UserProfile.objects.create(user=user, cargo=cargo)
        return user

    def iniciar_sesion(self, user):
        """Deja la sesion como la deja la vista de login (clave 'logueado')."""
        session = self.client.session
        session["logueado"] = {
            "id": user.id,
            "nombre": user.first_name or user.username,
            "rol": user.profile.cargo,
        }
        session.save()
        return session

    def crear_producto(self, sku="1", nombre="Cafe molido", precio=5000, stock=10, stock_minimo=2):
        categoria, _ = Categoria.objects.get_or_create(nombre="General")
        producto = Product.objects.create(
            sku=sku,
            nombre=nombre,
            precio_venta=precio,
            categoria=categoria,
        )
        inventario = Inventory.objects.create(
            product=producto,
            branch=self.branch,
            cantidad_disponible=stock,
            stock_minimo=stock_minimo,
        )
        return producto, inventario

    def crear_cliente(self, nombre="Cliente Uno", correo="cliente1@test.com"):
        return Cliente.objects.create(
            nombre=nombre,
            correo=correo,
            telefono="3001234567",
            direccion="Calle 1",
        )
