from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.db import IntegrityError
from django.db.models import Sum
from .models import (
    UserProfile, Branch, Product, Inventory, InventoryLog,
    Cliente, Proveedor, ProveedorProducto,
    Factura, FacturaDetalle, Pedido, PedidoDetalle,
    Notificacion, ChatHistorial,
)
from .servicio_ia import consultar_asistente_effiadmi
import functools


def autorizacion(cargos_permitidos=None):
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.session.get("logueado"):
                return redirect("effiadmi:login")
            
            if cargos_permitidos:
                rol_usuario = request.session.get("logueado", {}).get("rol")
                if rol_usuario not in cargos_permitidos:
                    messages.error(request, "No tienes permisos para acceder a esta seccion.")
                    return redirect("effiadmi:inicio")
            
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ==================== LOGIN/LOGOUT ====================


def login(request):
    if request.method == "POST":
        email = request.POST.get("username")
        contrasena = request.POST.get("password")

        try:
            user = authenticate(request, username=email, password=contrasena)
            if user is not None:
                auth_login(request, user)
                messages.success(request, f"¡Bienvenido, {user.first_name or user.username}!")

                perfil = UserProfile.objects.filter(user=user).first()
                cargo = perfil.cargo if perfil else "operador"

                request.session["logueado"] = {
                    "id": user.id,
                    "nombre": user.first_name or user.username,
                    "rol": cargo,
                }
                return redirect("effiadmi:inicio")
            else:
                messages.error(request, "Usuario o contraseña incorrectos...")
                return redirect("effiadmi:login")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return redirect("effiadmi:login")

    if request.session.get("logueado", False):
        return redirect("effiadmi:inicio")
    return render(request, "usuarios/login.html")


@autorizacion()
def logout(request):
    try:
        auth_logout(request)
        request.session.flush()
        messages.success(request, "¡Sesion cerrada exitosamente!")
        return redirect("effiadmi:login")
    except Exception as e:
        messages.warning(request, f"Error al cerrar sesion: {str(e)}")
        return redirect("effiadmi:inicio")


# ==================== DASHBOARD ====================


@autorizacion()
def inicio(request):
    try:
        total_productos = Product.objects.count()
        total_clientes = Cliente.objects.count()
        total_facturas = Factura.objects.count()
        total_pedidos = Pedido.objects.count()

        inventario = Inventory.objects.all()
        unidades_totales = inventario.aggregate(total=Sum("cantidad_disponible"))["total"] or 0
        valor_inventario = 0
        productos_bajo_stock = []

        for inv in inventario.select_related("product"):
            valor_inventario += float(inv.product.precio_venta) * inv.cantidad_disponible
            if inv.cantidad_disponible <= inv.stock_minimo:
                productos_bajo_stock.append(inv)

        movimientos_recientes = InventoryLog.objects.select_related(
            "inventory__product", "inventory__branch"
        ).order_by("-fecha")[:10]

        contexto = {
            "total_productos": total_productos,
            "total_clientes": total_clientes,
            "total_facturas": total_facturas,
            "total_pedidos": total_pedidos,
            "unidades_totales": unidades_totales,
            "valor_inventario": valor_inventario,
            "productos_bajo_stock": productos_bajo_stock,
            "movimientos_recientes": movimientos_recientes,
        }
        return render(request, "dashboard/index.html", contexto)
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return render(request, "dashboard/index.html")


@autorizacion()
def perfil(request):
    user = User.objects.get(pk=request.session.get("logueado", {}).get("id"))
    perfil, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        user.first_name = request.POST.get("nombre", "")
        user.last_name = request.POST.get("apellido", "")
        user.email = request.POST.get("email", "")
        user.save()

        perfil.telefono = request.POST.get("telefono", "")
        perfil.direccion = request.POST.get("direccion", "")
        perfil.save()

        request.session["logueado"]["nombre"] = user.first_name or user.username

        messages.success(request, "¡Perfil actualizado exitosamente!")
        return redirect("effiadmi:perfil")

    return render(request, "usuarios/perfil.html", {"usuario": user, "perfil": perfil})


# ==================== CLIENTES ====================

@autorizacion()
def lista_clientes(request):
    try:
        clientes_registrados = Cliente.objects.all().order_by("-id")
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

            Cliente.objects.create(
                nombre=nombre,
                correo=correo,
                telefono=telefono,
                direccion=direccion,
            )
            messages.success(request, "¡Cliente creado exitosamente!")
            return redirect("effiadmi:lista_clientes")
        except IntegrityError:
            messages.error(request, "El correo ya esta registrado.")
            return render(request, "clientes/formulario_clientes.html")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "clientes/formulario_clientes.html")

    return render(request, "clientes/formulario_clientes.html")


@autorizacion()
def editar_cliente(request, id):
    try:
        cliente = get_object_or_404(Cliente, pk=id)

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
        cliente = get_object_or_404(Cliente, pk=id)
        if request.method == "POST":
            cliente.delete()
            messages.success(request, "¡Cliente eliminado exitosamente!")
        return redirect("effiadmi:lista_clientes")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_clientes")


# ==================== PRODUCTOS ====================

@autorizacion()
def lista_productos(request):
    try:
        productos_registrados = Product.objects.all().order_by("-id")

        stock_map = {}
        for inv in Inventory.objects.select_related("branch").all():
            pid = inv.product.id
            if pid not in stock_map:
                stock_map[pid] = 0
            stock_map[pid] += inv.cantidad_disponible

        productos_con_stock = []
        for p in productos_registrados:
            productos_con_stock.append({
                "producto": p,
                "stock": stock_map.get(p.id, 0),
            })

        return render(request, "productos/lista.html", {"productos": productos_con_stock})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_producto(request):
    sucursales = Branch.objects.all()

    if request.method == "POST":
        try:
            sku = request.POST.get("sku")
            nombre = request.POST.get("nombre")
            descripcion = request.POST.get("descripcion")
            categoria = request.POST.get("categoria")
            precio_venta = request.POST.get("precio_venta")
            sucursal_id = request.POST.get("sucursal")
            stock_inicial = request.POST.get("stock_inicial", 0)
            stock_minimo = request.POST.get("stock_minimo", 5)

            if not all([sku, nombre, precio_venta]):
                messages.error(request, "Por favor completa los campos obligatorios.")
                return render(request, "productos/crear.html", {"sucursales": sucursales})

            branch = None
            if sucursal_id:
                branch = Branch.objects.filter(id=sucursal_id).first()
            if not branch:
                branch = Branch.objects.filter(es_principal=True).first()
            if not branch:
                branch = Branch.objects.create(nombre="Sucursal Principal", es_principal=True)

            producto = Product.objects.create(
                sku=sku,
                nombre=nombre,
                descripcion=descripcion or "",
                categoria=categoria or "",
                precio_venta=float(precio_venta),
            )

            inventario = Inventory.objects.create(
                product=producto,
                branch=branch,
                cantidad_disponible=int(stock_inicial),
                stock_minimo=int(stock_minimo),
            )

            if int(stock_inicial) > 0:
                usuario = None
                if request.session.get("logueado"):
                    usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()
                InventoryLog.objects.create(
                    inventory=inventario,
                    tipo_movimiento="ENTRADA",
                    cantidad=int(stock_inicial),
                    cantidad_resultante=int(stock_inicial),
                    motivo="Creacion automatica de producto con stock inicial",
                    usuario=usuario,
                )

            messages.success(request, "¡Producto creado exitosamente!")
            return redirect("effiadmi:lista_productos")
        except IntegrityError:
            messages.error(request, "El SKU ya esta registrado.")
            return render(request, "productos/crear.html", {"sucursales": sucursales})
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "productos/crear.html", {"sucursales": sucursales})

    return render(request, "productos/crear.html", {"sucursales": sucursales})


@autorizacion()
def editar_producto(request, id):
    try:
        producto = get_object_or_404(Product, pk=id)
        sucursales = Branch.objects.all()

        if request.method == "POST":
            producto.sku = request.POST.get("sku")
            producto.nombre = request.POST.get("nombre")
            producto.descripcion = request.POST.get("descripcion", "")
            producto.categoria = request.POST.get("categoria", "")
            producto.precio_venta = float(request.POST.get("precio_venta"))
            producto.save()
            messages.success(request, "¡Producto actualizado exitosamente!")
            return redirect("effiadmi:lista_productos")

        return render(request, "productos/editar.html", {"producto": producto, "sucursales": sucursales})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_productos")


@autorizacion()
def eliminar_producto(request, id):
    try:
        producto = get_object_or_404(Product, pk=id)
        if request.method == "POST":
            producto.delete()
            messages.success(request, "¡Producto eliminado exitosamente!")
        return redirect("effiadmi:lista_productos")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_productos")


# ==================== INVENTARIO ====================

@autorizacion()
def lista_inventario(request):
    try:
        sucursal_id = request.GET.get("sucursal")
        categoria = request.GET.get("categoria")

        inventario = Inventory.objects.select_related("product", "branch").all()

        if sucursal_id:
            inventario = inventario.filter(branch_id=sucursal_id)
        if categoria:
            inventario = inventario.filter(product__categoria=categoria)

        inventario = inventario.order_by("product__categoria", "product__nombre")

        sucursales = Branch.objects.all()
        categorias = Product.objects.values_list("categoria", flat=True).distinct().exclude(categoria="")

        contexto = {
            "inventario": inventario,
            "sucursales": sucursales,
            "categorias": list(categorias),
            "sucursal_seleccionada": sucursal_id,
            "categoria_seleccionada": categoria,
        }
        return render(request, "inventario/lista.html", contexto)
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def detalle_inventario(request, id):
    try:
        inventario = get_object_or_404(
            Inventory.objects.select_related("product", "branch"), pk=id
        )
        movimientos = InventoryLog.objects.filter(inventory=inventario).order_by("-fecha")[:50]

        contexto = {
            "inventario": inventario,
            "movimientos": movimientos,
        }
        return render(request, "inventario/detalle.html", contexto)
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_inventario")


@autorizacion()
def registrar_movimiento(request, id):
    try:
        inventario = get_object_or_404(
            Inventory.objects.select_related("product", "branch"), pk=id
        )

        if request.method == "POST":
            tipo = request.POST.get("tipo_movimiento")
            cantidad = int(request.POST.get("cantidad", 0))
            motivo = request.POST.get("motivo", "")

            if tipo == "ENTRADA":
                inventario.cantidad_disponible += cantidad
            elif tipo == "SALIDA":
                if inventario.cantidad_disponible < cantidad:
                    messages.error(request, f"Stock insuficiente. Disponible: {inventario.cantidad_disponible}")
                    return redirect("effiadmi:registrar_movimiento", id=inventario.id)
                inventario.cantidad_disponible -= cantidad
            elif tipo == "AJUSTE":
                inventario.cantidad_disponible = cantidad

            inventario.save()

            usuario = None
            if request.session.get("logueado"):
                usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()

            InventoryLog.objects.create(
                inventory=inventario,
                tipo_movimiento=tipo,
                cantidad=cantidad,
                cantidad_resultante=inventario.cantidad_disponible,
                motivo=motivo,
                usuario=usuario,
            )

            if inventario.cantidad_disponible <= inventario.stock_minimo:
                messages.warning(request, f"¡Alerta! Stock bajo para '{inventario.product.nombre}' ({inventario.cantidad_disponible}/{inventario.stock_minimo})")

            messages.success(request, f"¡{tipo} registrada exitosamente!")
            return redirect("effiadmi:detalle_inventario", id=inventario.id)

        return render(request, "inventario/movimientos.html", {"inventario": inventario})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_inventario")


# ==================== FACTURAS ====================

@autorizacion()
def lista_facturas(request):
    try:
        facturas_registradas = Factura.objects.select_related("cliente").all().order_by("-id")
        return render(request, "facturas/lista.html", {"facturas": facturas_registradas})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_factura(request):
    try:
        clientes_registrados = Cliente.objects.all().order_by("nombre")
        productos_disponibles = Product.objects.all().order_by("nombre")

        if request.method == "POST":
            cliente = get_object_or_404(Cliente, pk=request.POST.get("cliente"))
            usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()

            factura = Factura.objects.create(
                cliente=cliente,
                usuario=usuario,
                total=0,
            )

            total = 0
            productos_ids = request.POST.getlist("producto")
            cantidades = request.POST.getlist("cantidad")
            precios = request.POST.getlist("precio_unitario")

            for i in range(len(productos_ids)):
                producto = Product.objects.get(pk=productos_ids[i])
                cantidad = int(cantidades[i])
                precio = float(precios[i])
                subtotal = cantidad * precio

                FacturaDetalle.objects.create(
                    factura=factura,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal,
                )
                total += subtotal

            factura.total = total
            factura.save()

            messages.success(request, "¡Factura creada exitosamente!")
            return redirect("effiadmi:lista_facturas")

        return render(request, "facturas/crear.html", {"clientes": clientes_registrados, "productos": productos_disponibles})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion()
def detalle_factura(request, id):
    try:
        factura = get_object_or_404(
            Factura.objects.select_related("cliente", "usuario"), pk=id
        )
        detalles = FacturaDetalle.objects.filter(factura=factura).select_related("producto")
        return render(request, "facturas/detalle.html", {"factura": factura, "detalles": detalles})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion()
def editar_factura(request, id):
    try:
        factura = get_object_or_404(Factura, pk=id)
        clientes_registrados = Cliente.objects.all().order_by("nombre")

        if request.method == "POST":
            factura.cliente = get_object_or_404(Cliente, pk=request.POST.get("cliente"))
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
        factura = get_object_or_404(Factura, pk=id)
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
        pedidos_registrados = Pedido.objects.select_related("cliente").all().order_by("-id")
        return render(request, "pedidos/lista.html", {"pedidos": pedidos_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_pedido(request):
    try:
        clientes_registrados = Cliente.objects.all().order_by("nombre")
        productos_disponibles = Product.objects.all().order_by("nombre")

        if request.method == "POST":
            cliente = get_object_or_404(Cliente, pk=request.POST.get("cliente"))
            usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()

            pedido = Pedido.objects.create(
                cliente=cliente,
                usuario=usuario,
                estado="pendiente",
                total=0,
            )

            total = 0
            productos_ids = request.POST.getlist("producto")
            cantidades = request.POST.getlist("cantidad")
            precios = request.POST.getlist("precio_unitario")

            for i in range(len(productos_ids)):
                producto = Product.objects.get(pk=productos_ids[i])
                cantidad = int(cantidades[i])
                precio = float(precios[i])
                subtotal = cantidad * precio

                PedidoDetalle.objects.create(
                    pedido=pedido,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal,
                )
                total += subtotal

            pedido.total = total
            pedido.save()

            messages.success(request, "¡Pedido creado exitosamente!")
            return redirect("effiadmi:lista_pedidos")

        return render(request, "pedidos/crear.html", {"clientes": clientes_registrados, "productos": productos_disponibles})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion()
def detalle_pedido(request, id):
    try:
        pedido = get_object_or_404(
            Pedido.objects.select_related("cliente", "usuario"), pk=id
        )
        detalles = PedidoDetalle.objects.filter(pedido=pedido).select_related("producto")
        return render(request, "pedidos/detalle.html", {"pedido": pedido, "detalles": detalles})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion()
def editar_pedido(request, id):
    try:
        pedido = get_object_or_404(Pedido, pk=id)
        clientes_registrados = Cliente.objects.all().order_by("nombre")

        if request.method == "POST":
            pedido.cliente = get_object_or_404(Cliente, pk=request.POST.get("cliente"))
            pedido.estado = request.POST.get("estado", pedido.estado)
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
        pedido = get_object_or_404(Pedido, pk=id)
        if request.method == "POST":
            pedido.delete()
            messages.success(request, "¡Pedido eliminado exitosamente!")
        return redirect("effiadmi:lista_pedidos")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


# ==================== USUARIOS ====================

@autorizacion(cargos_permitidos=["admin"])
def lista_usuarios(request):
    try:
        usuarios_registrados = User.objects.select_related("profile").all().order_by("-id")
        return render(request, "usuarios/lista.html", {"usuarios": usuarios_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(cargos_permitidos=["admin"])
def crear_usuario(request):
    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre_usuario")
            apellido = request.POST.get("apellido_usuario")
            email = request.POST.get("email")
            contrasena = request.POST.get("contraseña")
            cargo = request.POST.get("cargo", "operador")

            if not all([nombre, email, contrasena]):
                messages.error(request, "Por favor completa todos los campos.")
                return render(request, "usuarios/crear.html")

            if User.objects.filter(email=email).exists():
                messages.error(request, "El correo ya esta registrado.")
                return render(request, "usuarios/crear.html")

            user = User.objects.create_user(
                username=email,
                email=email,
                password=contrasena,
                first_name=nombre,
                last_name=apellido or "",
            )

            UserProfile.objects.create(user=user, cargo=cargo)

            messages.success(request, "¡Usuario creado exitosamente!")
            return redirect("effiadmi:lista_usuarios")
        except IntegrityError:
            messages.error(request, "El correo ya esta registrado.")
            return render(request, "usuarios/crear.html")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "usuarios/crear.html")

    return render(request, "usuarios/crear.html")


@autorizacion(cargos_permitidos=["admin"])
def editar_usuario(request, id):
    try:
        user = get_object_or_404(User, pk=id)
        perfil, _ = UserProfile.objects.get_or_create(user=user)

        if request.method == "POST":
            user.first_name = request.POST.get("nombre_usuario", "")
            user.last_name = request.POST.get("apellido_usuario", "")
            user.email = request.POST.get("email", "")

            nueva_contrasena = request.POST.get("contraseña")
            if nueva_contrasena:
                user.set_password(nueva_contrasena)

            user.save()

            perfil.cargo = request.POST.get("cargo", perfil.cargo)
            perfil.save()

            messages.success(request, "¡Usuario actualizado exitosamente!")
            return redirect("effiadmi:lista_usuarios")

        return render(request, "usuarios/editar.html", {"usuario": user, "perfil": perfil})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_usuarios")


@autorizacion(cargos_permitidos=["admin"])
def eliminar_usuario(request, id):
    try:
        user = get_object_or_404(User, pk=id)
        if request.method == "POST":
            user.delete()
            messages.success(request, "¡Usuario eliminado exitosamente!")
        return redirect("effiadmi:lista_usuarios")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_usuarios")


# ==================== PROVEEDORES ====================

@autorizacion()
def lista_proveedores(request):
    try:
        proveedores_registrados = Proveedor.objects.all().order_by("-id")
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

            Proveedor.objects.create(
                nombre=nombre,
                correo=correo,
                telefono=telefono,
                direccion=direccion,
            )
            messages.success(request, "¡Proveedor creado exitosamente!")
            return redirect("effiadmi:lista_proveedores")
        except IntegrityError:
            messages.error(request, "El correo ya esta registrado.")
            return render(request, "proveedores/crear.html")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "proveedores/crear.html")

    return render(request, "proveedores/crear.html")


@autorizacion()
def editar_proveedor(request, id):
    try:
        proveedor = get_object_or_404(Proveedor, pk=id)

        if request.method == "POST":
            proveedor.nombre = request.POST.get("nombre_proveedor")
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
        proveedor = get_object_or_404(Proveedor, pk=id)
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
        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()
        notificaciones_registradas = Notificacion.objects.filter(usuario=usuario).order_by("-id")
        return render(request, "notificaciones/lista.html", {"notificaciones": notificaciones_registradas})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def detalle_notificacion(request, id):
    try:
        notif = get_object_or_404(Notificacion, pk=id)
        
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
        notif = get_object_or_404(Notificacion, pk=id)
        if request.method == "POST":
            notif.delete()
            messages.success(request, "¡Notificacion eliminada exitosamente!")
        return redirect("effiadmi:lista_notificaciones")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_notificaciones")


# ==================== REPORTES ====================

@autorizacion()
def reportes_view(request):
    try:
        return render(request, "reportes/index.html")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


# ==================== ESTADISTICAS IA ====================

@autorizacion()
def estadisticas_ia(request):
    try:
        total_productos = Product.objects.count()
        total_proveedores = Proveedor.objects.count()
        total_clientes = Cliente.objects.count()
        total_facturas = Factura.objects.count()

        inventario = Inventory.objects.all()
        unidades_totales = inventario.aggregate(total=Sum("cantidad_disponible"))["total"] or 0
        valor_inventario = 0
        productos_bajos = []

        for inv in inventario.select_related("product"):
            valor_inventario += float(inv.product.precio_venta) * inv.cantidad_disponible
            if inv.cantidad_disponible <= inv.stock_minimo:
                productos_bajos.append(inv)

        ventas_por_producto = (
            FacturaDetalle.objects
            .values("producto__id", "producto__nombre")
            .annotate(total=Sum("cantidad"))
            .order_by("-total")
        )
        producto_mas_vendido = None
        if ventas_por_producto:
            mejor = ventas_por_producto.first()
            producto_mas_vendido = {
                "nombre": mejor["producto__nombre"],
                "unidades": mejor["total"],
            }

        contexto = {
            "total_productos": total_productos,
            "total_proveedores": total_proveedores,
            "total_clientes": total_clientes,
            "total_facturas": total_facturas,
            "unidades_totales": unidades_totales,
            "valor_inventario": valor_inventario,
            "productos_bajos": productos_bajos,
            "producto_mas_vendido": producto_mas_vendido,
            "entradas": InventoryLog.objects.filter(tipo_movimiento="ENTRADA").count(),
            "salidas": InventoryLog.objects.filter(tipo_movimiento="SALIDA").count(),
        }

        if request.method == "POST":
            pregunta = request.POST.get("pregunta", "").strip()
            if pregunta:
                contexto["respuesta_ia"] = consultar_asistente_effiadmi(pregunta)
                contexto["pregunta"] = pregunta
            else:
                messages.warning(request, "Escribe una pregunta para el asistente IA.")

        return render(request, "dashboard/estadisticas.html", contexto)
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


# ==================== CHAT IA ====================

@autorizacion()
def chat_ia(request):
    try:
        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()

        if request.method == "POST":
            pregunta = request.POST.get("mensaje", "").strip()
            if pregunta:
                historial_usuario = ChatHistorial.objects.filter(usuario=usuario).order_by("-fecha")[:10]

                contexto_ia = [
                    {"role": "system", "content": "Eres el asistente inteligente de EFFIADMI, un sistema de gestion para PYMES. Responde en espanol, de forma breve y practica."}
                ]
                for h in reversed(historial_usuario):
                    contexto_ia.append({"role": "user", "content": h.mensaje})
                    contexto_ia.append({"role": "assistant", "content": h.respuesta})
                contexto_ia.append({"role": "user", "content": pregunta})

                respuesta = consultar_asistente_effiadmi(pregunta)

                ChatHistorial.objects.create(
                    usuario=usuario,
                    mensaje=pregunta,
                    respuesta=respuesta,
                )

                messages.success(request, "Pregunta enviada.")
            else:
                messages.warning(request, "Escribe una pregunta.")

        historial = ChatHistorial.objects.filter(usuario=usuario).order_by("-fecha")[:20]
        return render(request, "dashboard/chat_ia.html", {"historial": historial})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")
