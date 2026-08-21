from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User


# ============================================================
# Perfil de usuario extendido (usa auth.User de Django)
# ============================================================

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    telefono = models.CharField(max_length=20, blank=True, default="")
    direccion = models.CharField(max_length=200, blank=True, default="")

    CARGOS = [
        ("admin", "Administrador"),
        ("operador", "Operador"),
    ]
    cargo = models.CharField(max_length=20, choices=CARGOS, default="operador")

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.cargo})"


# ============================================================
# Sucursales
# ============================================================

class Branch(models.Model):
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=250, blank=True, default="")
    es_principal = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"

    def __str__(self):
        return self.nombre


# ============================================================
# Productos (catálogo general)
# ============================================================

class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True, db_index=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default="")
    categoria = models.CharField(max_length=100, blank=True, default="", db_index=True)
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]

    def __str__(self):
        return f"[{self.sku}] {self.nombre}"

    def clean(self):
        errors = {}
        if self.precio_venta is not None and self.precio_venta <= 0:
            errors["precio_venta"] = "El precio de venta debe ser mayor a 0."
        if errors:
            raise ValidationError(errors)


# ============================================================
# Inventario (existencias por sucursal)
# ============================================================

class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="inventories")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="inventories")
    cantidad_disponible = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=5)

    class Meta:
        verbose_name = "Inventario"
        verbose_name_plural = "Inventarios"
        unique_together = ("product", "branch")

    def __str__(self):
        return f"{self.product.nombre} - {self.branch.nombre}: {self.cantidad_disponible}"


# ============================================================
# Kardex / Historial de movimientos de inventario
# ============================================================

class InventoryLog(models.Model):
    ENTRADA = "ENTRADA"
    SALIDA = "SALIDA"
    AJUSTE = "AJUSTE"
    TIPO_MOVIMIENTO_CHOICES = [
        (ENTRADA, "Entrada"),
        (SALIDA, "Salida"),
        (AJUSTE, "Ajuste"),
    ]

    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name="logs")
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO_CHOICES)
    cantidad = models.IntegerField()
    cantidad_resultante = models.IntegerField()
    motivo = models.TextField(blank=True, default="")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["-fecha"]),
            models.Index(fields=["tipo_movimiento"]),
        ]

    def __str__(self):
        return f"{self.tipo_movimiento} x{self.cantidad} -> {self.inventory}"


# ============================================================
# Clientes
# ============================================================

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    correo = models.EmailField(unique=True, db_index=True)
    telefono = models.CharField(max_length=20)
    direccion = models.CharField(max_length=200)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.nombre


# ============================================================
# Proveedores
# ============================================================

class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    correo = models.EmailField(unique=True, db_index=True)
    telefono = models.CharField(max_length=20)
    direccion = models.CharField(max_length=200)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

    def __str__(self):
        return self.nombre


# ============================================================
# Relación Proveedor - Producto
# ============================================================

class ProveedorProducto(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name="productos")
    producto = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="proveedores")
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Proveedor-Producto"
        verbose_name_plural = "Proveedor-Productos"
        unique_together = ("proveedor", "producto")

    def __str__(self):
        return f"{self.proveedor.nombre} -> {self.producto.nombre}"


# ============================================================
# Pedidos
# ============================================================

class Pedido(models.Model):
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("confirmado", "Confirmado"),
        ("pagado", "Pagado"),
        ("cancelado", "Cancelado"),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="pedidos")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_pedido = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-fecha_pedido"]

    def __str__(self):
        return f"Pedido {self.id} - {self.cliente.nombre} ({self.estado})"


class PedidoDetalle(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Product, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Detalle de Pedido"
        verbose_name_plural = "Detalles de Pedido"

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)


# ============================================================
# Facturas
# ============================================================

class Factura(models.Model):
    ESTADO_CHOICES = [
        ("emitida", "Emitida"),
        ("anulada", "Anulada"),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="facturas")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    pedido = models.ForeignKey(Pedido, on_delete=models.SET_NULL, null=True, blank=True, related_name="facturas")
    fecha_emision = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default="emitida")

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ["-fecha_emision"]

    def __str__(self):
        return f"Factura {self.id} - {self.cliente.nombre}"


class FacturaDetalle(models.Model):
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Product, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Detalle de Factura"
        verbose_name_plural = "Detalles de Factura"

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)


# ============================================================
# Notificaciones (por usuario)
# ============================================================

class Notificacion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notificaciones")
    mensaje = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Notificacion"
        verbose_name_plural = "Notificaciones"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Notificacion {self.id} - {self.usuario.username}"


# ============================================================
# Historial de chat con IA
# ============================================================

class ChatHistorial(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_historial")
    mensaje = models.TextField()
    respuesta = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Chat con IA"
        verbose_name_plural = "Chats con IA"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Chat {self.usuario.username} - {self.fecha}"
