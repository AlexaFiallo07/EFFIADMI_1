from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.db import IntegrityError
from django.db.models import Sum
from .models import Clientes, Usuario, facturas, pedidos, Inventario, productos, proveedores, notificaciones, movimientos
from .servicio_ia import consultar_asistente_effiadmi
import functools


def autorizacion(cargos_permitidos=None):
    """Authorization decorator that requires a logged-in session and optionally checks roles."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.session.get("logueado"):
                return redirect("effiadmi:login")
            
            if cargos_permitidos:
                rol_usuario = request.session.get("logueado", {}).get("rol")
                if rol_usuario not in cargos_permitidos:
                    messages.error(request, "No tienes permisos para acceder a esta sección.")
                    return redirect("effiadmi:inicio")
            
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ==================== LOGIN/LOGOUT ====================


def login(request):
    if request.method == "POST":
        usuario = request.POST.get("username")
        contrasena = request.POST.get("password")

        try:
            u = Usuario.objects.get(email=usuario, contraseña=contrasena)
            messages.success(request, f"¡Bienvenido, {u.nombre_usuario}!")

            request.session["logueado"] = {
                "id": u.id,
                "nombre": f"{u.nombre_usuario}",
                "rol": u.cargo,
            }
            return redirect("effiadmi:inicio")
        except Usuario.DoesNotExist:
            messages.error(request, "Usuario o contraseña incorrectos...")
            request.session["logueado"] = None
            return redirect("effiadmi:login")

    if request.session.get("logueado", False):
        return redirect("effiadmi:inicio")
    return render(request, "usuarios/login.html")


@autorizacion()
def logout(request):
    try:
        del request.session["logueado"]
        messages.success(request, "¡Sesión cerrada exitosamente!")
        return redirect("effiadmi:login")
    except Exception as e:
        messages.warning(request, f"Error al cerrar sesión: {str(e)}")
        return redirect("effiadmi:inicio")


# ==================== DASHBOARD ====================

@autorizacion()
def inicio(request):
    return render(request, "dashboard/index.html")


@autorizacion()
def perfil(request):
    usuario_id = request.session.get("logueado", {}).get("id")
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    if request.method == "POST":
        usuario.nombre_usuario = request.POST.get("nombre_usuario")
        usuario.apellido_usuario = request.POST.get("apellido_usuario")
        usuario.email = request.POST.get("email")
        usuario.cargo = request.POST.get("cargo")

        nueva_contrasena = request.POST.get("contrasena")
        if nueva_contrasena:
            usuario.contraseña = nueva_contrasena

        usuario.save()
        request.session["logueado"] = {
            "id": usuario.id,
            "nombre": usuario.nombre_usuario,
            "rol": usuario.cargo,
        }
        messages.success(request, "¡Perfil actualizado exitosamente!")
        return redirect("effiadmi:perfil")

    return render(request, "usuarios/perfil.html", {"usuario": usuario})


# ==================== CLIENTES ====================

@autorizacion()
def lista_clientes(request):
    try:
        clientes_registrados = Clientes.objects.all().order_by("-id")
        return render(request, "clientes/lista_clientes.html", {"clientes": clientes_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_cliente(request):
    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre")
            correo = request.POST.get("correo")
            telefono = request.POST.get("telefono")
            direccion = request.POST.get("direccion")

            if not all([nombre, correo, telefono, direccion]):
                messages.error(request, "Por favor completa todos los campos.")
                return render(request, "clientes/formulario_clientes.html")

            Clientes.objects.create(
                nombre=nombre,
                correo=correo,
                telefono=telefono,
                direccion=direccion,
            )
            messages.success(request, "¡Cliente creado exitosamente!")
            return redirect("effiadmi:lista_clientes")
        except IntegrityError as e:
            messages.error(request, "Error de integridad en los datos.")
            return render(request, "clientes/formulario_clientes.html")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "clientes/formulario_clientes.html")

    return render(request, "clientes/formulario_clientes.html")


@autorizacion()
def editar_cliente(request, id):
    try:
        cliente = get_object_or_404(Clientes, pk=id)

        if request.method == "POST":
            cliente.nombre = request.POST.get("nombre")
            cliente.correo = request.POST.get("correo")
            cliente.telefono = request.POST.get("telefono")
            cliente.direccion = request.POST.get("direccion")
            cliente.save()
            messages.success(request, "¡Cliente actualizado exitosamente!")
            return redirect("effiadmi:lista_clientes")

        return render(request, "clientes/formulario_clientes.html", {"cliente": cliente})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_clientes")


@autorizacion()
def eliminar_cliente(request, id):
    try:
        cliente = get_object_or_404(Clientes, pk=id)
        if request.method == "POST":
            cliente.delete()
            messages.success(request, "¡Cliente eliminado exitosamente!")
        return redirect("effiadmi:lista_clientes")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_clientes")


# ==================== INVENTARIO ====================

@autorizacion()
def lista_inventario(request):
    try:
        inventario_registrado = Inventario.objects.all().order_by("-id")
        return render(request, "inventario/lista.html", {"inventario": inventario_registrado})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_inventario(request):
    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre_producto")
            stock_actual = request.POST.get("stock_actual")
            stock_minimo = request.POST.get("stock_minimo")
            precio_venta = request.POST.get("precio_venta")
            precio_compra = request.POST.get("precio_compra")
            descripcion = request.POST.get("descripcion")

            if not all([nombre, stock_actual, stock_minimo, precio_venta, precio_compra, descripcion]):
                messages.error(request, "Por favor completa todos los campos.")
                return render(request, "inventario/crear.html")

            Inventario.objects.create(
                nombre_producto=nombre,
                stock_actual=int(stock_actual),
                stock_minimo=int(stock_minimo),
                precio_venta=float(precio_venta),
                precio_compra=float(precio_compra),
                descripcion=descripcion,
            )
            messages.success(request, "¡Producto de inventario creado exitosamente!")
            return redirect("effiadmi:lista_inventario")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "inventario/crear.html")

    return render(request, "inventario/crear.html")


@autorizacion()
def editar_inventario(request, id):
    try:
        item_inventario = get_object_or_404(Inventario, pk=id)

        if request.method == "POST":
            item_inventario.nombre_producto = request.POST.get("nombre_producto")
            item_inventario.stock_actual = int(request.POST.get("stock_actual"))
            item_inventario.stock_minimo = int(request.POST.get("stock_minimo"))
            item_inventario.precio_venta = float(request.POST.get("precio_venta"))
            item_inventario.precio_compra = float(request.POST.get("precio_compra"))
            item_inventario.descripcion = request.POST.get("descripcion")
            item_inventario.save()
            messages.success(request, "¡Inventario actualizado exitosamente!")
            return redirect("effiadmi:lista_inventario")

        return render(request, "inventario/editar.html", {"item": item_inventario})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_inventario")


@autorizacion()
def eliminar_inventario(request, id):
    try:
        item_inventario = get_object_or_404(Inventario, pk=id)
        if request.method == "POST":
            item_inventario.delete()
            messages.success(request, "¡Producto de inventario eliminado exitosamente!")
        return redirect("effiadmi:lista_inventario")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_inventario")


# ==================== PRODUCTOS ====================

@autorizacion()
def lista_productos(request):
    try:
        productos_registrados = productos.objects.all().order_by("-id")
        return render(request, "productos/lista.html", {"productos": productos_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_producto(request):
    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre_producto")
            descripcion = request.POST.get("descripcion")
            precio_venta = request.POST.get("precio_venta")
            precio_compra = request.POST.get("precio_compra")
            stock_actual = request.POST.get("stock_actual")
            stock_minimo = request.POST.get("stock_minimo")

            if not all([nombre, descripcion, precio_venta, precio_compra, stock_actual, stock_minimo]):
                messages.error(request, "Por favor completa todos los campos.")
                return render(request, "productos/crear.html")

            productos.objects.create(
                nombre_producto=nombre,
                descripcion=descripcion,
                precio_venta=float(precio_venta),
                precio_compra=float(precio_compra),
                stock_actual=int(stock_actual),
                stock_minimo=int(stock_minimo),
            )
            messages.success(request, "¡Producto creado exitosamente!")
            return redirect("effiadmi:lista_productos")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "productos/crear.html")

    return render(request, "productos/crear.html")


@autorizacion()
def editar_producto(request, id):
    try:
        producto = get_object_or_404(productos, pk=id)

        if request.method == "POST":
            producto.nombre_producto = request.POST.get("nombre_producto")
            producto.descripcion = request.POST.get("descripcion")
            producto.precio_venta = float(request.POST.get("precio_venta"))
            producto.precio_compra = float(request.POST.get("precio_compra"))
            producto.stock_actual = int(request.POST.get("stock_actual"))
            producto.stock_minimo = int(request.POST.get("stock_minimo"))
            producto.save()
            messages.success(request, "¡Producto actualizado exitosamente!")
            return redirect("effiadmi:lista_productos")

        return render(request, "productos/editar.html", {"producto": producto})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_productos")


@autorizacion()
def eliminar_producto(request, id):
    try:
        producto = get_object_or_404(productos, pk=id)
        if request.method == "POST":
            producto.delete()
            messages.success(request, "¡Producto eliminado exitosamente!")
        return redirect("effiadmi:lista_productos")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_productos")


# ==================== FACTURAS ====================

@autorizacion()
def lista_facturas(request):
    try:
        facturas_registradas = facturas.objects.select_related("cliente").all().order_by("-id")
        return render(request, "facturas/lista.html", {"facturas": facturas_registradas})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_factura(request):
    try:
        clientes_registrados = Clientes.objects.all().order_by("nombre")

        if request.method == "POST":
            cliente = get_object_or_404(Clientes, pk=request.POST.get("cliente"))
            total = request.POST.get("total")

            if not total:
                messages.error(request, "Por favor ingresa el total de la factura.")
                return render(request, "facturas/crear.html", {"clientes": clientes_registrados})

            facturas.objects.create(
                cliente=cliente,
                total=float(total),
            )
            messages.success(request, "¡Factura creada exitosamente!")
            return redirect("effiadmi:lista_facturas")

        return render(request, "facturas/crear.html", {"clientes": clientes_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion()
def detalle_factura(request, id):
    try:
        factura = get_object_or_404(facturas.objects.select_related("cliente"), pk=id)
        return render(request, "facturas/detalle.html", {"factura": factura})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion()
def editar_factura(request, id):
    try:
        factura = get_object_or_404(facturas, pk=id)
        clientes_registrados = Clientes.objects.all().order_by("nombre")

        if request.method == "POST":
            factura.cliente = get_object_or_404(Clientes, pk=request.POST.get("cliente"))
            factura.total = float(request.POST.get("total"))
            factura.save()
            messages.success(request, "¡Factura actualizada exitosamente!")
            return redirect("effiadmi:lista_facturas")

        return render(request, "facturas/editar.html", {"factura": factura, "clientes": clientes_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion()
def eliminar_factura(request, id):
    try:
        factura = get_object_or_404(facturas, pk=id)
        if request.method == "POST":
            factura.delete()
            messages.success(request, "¡Factura eliminada exitosamente!")
        return redirect("effiadmi:lista_facturas")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


# ==================== PEDIDOS ====================

@autorizacion()
def lista_pedidos(request):
    try:
        pedidos_registrados = pedidos.objects.select_related("cliente").all().order_by("-id")
        return render(request, "pedidos/lista.html", {"pedidos": pedidos_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_pedido(request):
    try:
        clientes_registrados = Clientes.objects.all().order_by("nombre")

        if request.method == "POST":
            cliente = get_object_or_404(Clientes, pk=request.POST.get("cliente"))
            total = request.POST.get("total")

            if not total:
                messages.error(request, "Por favor ingresa el total del pedido.")
                return render(request, "pedidos/crear.html", {"clientes": clientes_registrados})

            pedidos.objects.create(
                cliente=cliente,
                total=float(total),
            )
            messages.success(request, "¡Pedido creado exitosamente!")
            return redirect("effiadmi:lista_pedidos")

        return render(request, "pedidos/crear.html", {"clientes": clientes_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion()
def detalle_pedido(request, id):
    try:
        pedido = get_object_or_404(pedidos.objects.select_related("cliente"), pk=id)
        return render(request, "pedidos/detalle.html", {"pedido": pedido})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion()
def editar_pedido(request, id):
    try:
        pedido = get_object_or_404(pedidos, pk=id)
        clientes_registrados = Clientes.objects.all().order_by("nombre")

        if request.method == "POST":
            pedido.cliente = get_object_or_404(Clientes, pk=request.POST.get("cliente"))
            pedido.total = float(request.POST.get("total"))
            pedido.save()
            messages.success(request, "¡Pedido actualizado exitosamente!")
            return redirect("effiadmi:lista_pedidos")

        return render(request, "pedidos/editar.html", {"pedido": pedido, "clientes": clientes_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion()
def eliminar_pedido(request, id):
    try:
        pedido = get_object_or_404(pedidos, pk=id)
        if request.method == "POST":
            pedido.delete()
            messages.success(request, "¡Pedido eliminado exitosamente!")
        return redirect("effiadmi:lista_pedidos")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


# ==================== USUARIOS ====================

@autorizacion()
def lista_usuarios(request):
    try:
        usuarios_registrados = Usuario.objects.all().order_by("-id")
        return render(request, "usuarios/lista.html", {"usuarios": usuarios_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_usuario(request):
    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre_usuario")
            apellido = request.POST.get("apellido_usuario")
            email = request.POST.get("email")
            contrasena = request.POST.get("contraseña")
            cargo = request.POST.get("cargo")

            if not all([nombre, apellido, email, contrasena, cargo]):
                messages.error(request, "Por favor completa todos los campos.")
                return render(request, "usuarios/crear.html")

            Usuario.objects.create(
                nombre_usuario=nombre,
                apellido_usuario=apellido,
                email=email,
                contraseña=contrasena,
                cargo=cargo,
            )
            messages.success(request, "¡Usuario creado exitosamente!")
            return redirect("effiadmi:lista_usuarios")
        except IntegrityError:
            messages.error(request, "El correo ya está registrado.")
            return render(request, "usuarios/crear.html")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "usuarios/crear.html")

    return render(request, "usuarios/crear.html")


@autorizacion()
def editar_usuario(request, id):
    try:
        usuario = get_object_or_404(Usuario, pk=id)

        if request.method == "POST":
            usuario.nombre_usuario = request.POST.get("nombre_usuario")
            usuario.apellido_usuario = request.POST.get("apellido_usuario")
            usuario.email = request.POST.get("email")
            usuario.cargo = request.POST.get("cargo")
            
            nueva_contrasena = request.POST.get("contraseña")
            if nueva_contrasena:
                usuario.contraseña = nueva_contrasena
            
            usuario.save()
            messages.success(request, "¡Usuario actualizado exitosamente!")
            return redirect("effiadmi:lista_usuarios")

        return render(request, "usuarios/editar.html", {"usuario": usuario})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_usuarios")


@autorizacion()
def eliminar_usuario(request, id):
    try:
        usuario = get_object_or_404(Usuario, pk=id)
        if request.method == "POST":
            usuario.delete()
            messages.success(request, "¡Usuario eliminado exitosamente!")
        return redirect("effiadmi:lista_usuarios")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_usuarios")


# ==================== PROVEEDORES ====================

@autorizacion()
def lista_proveedores(request):
    try:
        proveedores_registrados = proveedores.objects.all().order_by("-id")
        return render(request, "proveedores/lista.html", {"proveedores": proveedores_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_proveedor(request):
    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre_proveedor")
            correo = request.POST.get("correo")
            telefono = request.POST.get("telefono")
            direccion = request.POST.get("direccion")

            if not all([nombre, correo, telefono, direccion]):
                messages.error(request, "Por favor completa todos los campos.")
                return render(request, "proveedores/crear.html")

            proveedores.objects.create(
                nombre_proveedor=nombre,
                correo=correo,
                telefono=telefono,
                direccion=direccion,
            )
            messages.success(request, "¡Proveedor creado exitosamente!")
            return redirect("effiadmi:lista_proveedores")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "proveedores/crear.html")

    return render(request, "proveedores/crear.html")


@autorizacion()
def editar_proveedor(request, id):
    try:
        proveedor = get_object_or_404(proveedores, pk=id)

        if request.method == "POST":
            proveedor.nombre_proveedor = request.POST.get("nombre_proveedor")
            proveedor.correo = request.POST.get("correo")
            proveedor.telefono = request.POST.get("telefono")
            proveedor.direccion = request.POST.get("direccion")
            proveedor.save()
            messages.success(request, "¡Proveedor actualizado exitosamente!")
            return redirect("effiadmi:lista_proveedores")

        return render(request, "proveedores/editar.html", {"proveedor": proveedor})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_proveedores")


@autorizacion()
def eliminar_proveedor(request, id):
    try:
        proveedor = get_object_or_404(proveedores, pk=id)
        if request.method == "POST":
            proveedor.delete()
            messages.success(request, "¡Proveedor eliminado exitosamente!")
        return redirect("effiadmi:lista_proveedores")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_proveedores")


# ==================== NOTIFICACIONES ====================

@autorizacion()
def lista_notificaciones(request):
    try:
        notificaciones_registradas = notificaciones.objects.all().order_by("-id")
        return render(request, "notificaciones/lista.html", {"notificaciones": notificaciones_registradas})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def detalle_notificacion(request, id):
    try:
        notif = get_object_or_404(notificaciones, pk=id)
        
        if not notif.leido:
            notif.leido = True
            notif.save()
        
        return render(request, "notificaciones/detalle.html", {"notificacion": notif})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_notificaciones")


@autorizacion()
def eliminar_notificacion(request, id):
    try:
        notif = get_object_or_404(notificaciones, pk=id)
        if request.method == "POST":
            notif.delete()
            messages.success(request, "¡Notificación eliminada exitosamente!")
        return redirect("effiadmi:lista_notificaciones")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_notificaciones")



# ==================== ESTADISTICAS IA ====================

@autorizacion()
def estadisticas_ia(request):
    try:
        total_productos = productos.objects.count()
        total_proveedores = proveedores.objects.count()
        total_usuarios = Usuario.objects.count()
        total_clientes = Clientes.objects.count()

        unidades_totales = 0
        valor_inventario = 0
        productos_bajos = []
        for producto in productos.objects.all():
            unidades_totales += producto.stock_actual
            valor_inventario += float(producto.precio_compra) * producto.stock_actual
            if producto.stock_actual < producto.stock_minimo:
                productos_bajos.append(producto)

        ventas_por_producto = (
            movimientos.objects
            .filter(tipo='salida')
            .values('producto')
            .annotate(total=Sum('cantidad'))
            .order_by('-total')
        )
        producto_mas_vendido = None
        if ventas_por_producto:
            mejor = ventas_por_producto.first()
            producto_obj = productos.objects.filter(id=mejor['producto']).first()
            if producto_obj:
                producto_mas_vendido = {
                    'nombre': producto_obj.nombre_producto,
                    'unidades': mejor['total'],
                }

        contexto = {
            'total_productos': total_productos,
            'total_proveedores': total_proveedores,
            'total_usuarios': total_usuarios,
            'total_clientes': total_clientes,
            'unidades_totales': unidades_totales,
            'valor_inventario': valor_inventario,
            'productos_bajos': productos_bajos,
            'producto_mas_vendido': producto_mas_vendido,
            'entradas': movimientos.objects.filter(tipo='entrada').count(),
            'salidas': movimientos.objects.filter(tipo='salida').count(),
        }

        if request.method == "POST":
            pregunta = request.POST.get("pregunta", "").strip()
            if pregunta:
                contexto['respuesta_ia'] = consultar_asistente_effiadmi(pregunta)
                contexto['pregunta'] = pregunta
            else:
                messages.warning(request, "Escribe una pregunta para el asistente IA.")

        return render(request, "dashboard/estadisticas.html", contexto)
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")
