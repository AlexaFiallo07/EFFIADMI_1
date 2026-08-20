from django.db import models

# Create your models here.
class Clientes(models.Model):
    nombre = models.CharField(max_length=100)
    correo = models.EmailField()
    telefono = models.CharField(max_length=20)
    direccion = models.CharField(max_length=200)

    def __str__(self):
        return self.nombre
    
class Inventario(models.Model):
    nombre_producto = models.CharField(max_length=100)
    stock_actual = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=5)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre_producto
    
class Usuario(models.Model):
    nombre_usuario = models.CharField(max_length=100)
    apellido_usuario = models.CharField(max_length=100)
    email = models.EmailField()
    contraseña = models.CharField(max_length=100)

    fecha_registro = models.DateTimeField(help_text="yyyy-mm-dd hh:mm:ss", auto_now_add=True)

    CARGOS = (
        ("Admin", "ADMINISTRADOR"),
        ("Operador", "OPERADOR"),
    )
    cargo = models.CharField(max_length=20, choices=CARGOS, default="Operador")

    def __str__(self):
        return f"{self.nombre_usuario} {self.apellido_usuario}"

class facturas(models.Model):
    cliente = models.ForeignKey(Clientes, on_delete=models.CASCADE)
    fecha_emision = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Factura {self.id} - Cliente: {self.cliente.nombre}"
    
class notificaciones(models.Model):
    mensaje = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    def __str__(self):
        return f"Notificación {self.id} - Leído: {self.leido}"
    
class pedidos(models.Model):
    cliente = models.ForeignKey(Clientes, on_delete=models.CASCADE)
    fecha_pedido = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Pedido {self.id} - Cliente: {self.cliente.nombre}"
    
class productos(models.Model):
    nombre_producto = models.CharField(max_length=100)
    descripcion = models.TextField()
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2)
    stock_actual = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=5)

    def __str__(self):
        return self.nombre_producto

class movimientos(models.Model):
    producto = models.ForeignKey(productos, on_delete=models.CASCADE, related_name='movimientos')
    TIPOS = (
        ("entrada", "ENTRADA"),
        ("salida", "SALIDA"),
        ("ajuste", "AJUSTE"),
    )
    tipo = models.CharField(max_length=20, choices=TIPOS)
    cantidad = models.IntegerField()
    descripcion = models.TextField(blank=True, default="")
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.tipo} - {self.producto.nombre_producto} x{self.cantidad}"

class proveedores(models.Model):
    nombre_proveedor = models.CharField(max_length=100)
    correo = models.EmailField()
    telefono = models.CharField(max_length=20)
    direccion = models.CharField(max_length=200)

    def __str__(self):
        return self.nombre_proveedor


# ============================================================
# Nuevos modelos: Branch, Product, Inventory, InventoryLog
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


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True, db_index=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default="")
    categoria = models.CharField(max_length=100, blank=True, default="")
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]

    def __str__(self):
        return f"[{self.sku}] {self.nombre}"


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
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.tipo_movimiento} x{self.cantidad} -> {self.inventory}"