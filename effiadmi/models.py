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

class reportes(models.Model):
    titulo = models.CharField(max_length=100)
    contenido = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo