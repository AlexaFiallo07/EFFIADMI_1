from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.db import IntegrityError, transaction
from django.db.models import Sum, F, Count
from django.utils import timezone
from datetime import timedelta
from django import template as django_template

register = django_template.Library()


def _formato_colombiano(value, decimales=False):
    try:
        numero = float(value)
    except (TypeError, ValueError):
        return value
    if decimales:
        return f"{numero:,.2f}".replace(",", ".").replace(".", ",", 1)
    return f"{int(round(numero)):,}".replace(",", ".")


@register.filter(name="cop")
def cop(value):
    return f"$ {_formato_colombiano(value)}"


@register.filter(name="cop_decimal")
def cop_decimal(value):
    return f"$ {_formato_colombiano(value, decimales=True)}"


@register.filter(name="marklight")
def marklight(value):
    from django.utils.html import escape
    from django.utils.safestring import mark_safe
    import re

    texto = escape(str(value) if value is not None else "")
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"`(.+?)`", r"<code>\1</code>", texto)
    return mark_safe(texto)
from .models import (
    UserProfile, Branch, Product, Categoria, Inventory, InventoryLog,
    Cliente, Proveedor, ProveedorProducto,
    Factura, FacturaDetalle, Pedido, PedidoDetalle,
    Notificacion, ChatHistorial, Reporte,
)
from .servicio_ia import consultar_asistente_effiadmi
from .utilidades import autorizacion, crear_notificacion, ids_admins


# ==================== LOGIN/LOGOUT ====================


def login(request):
    if request.method == "POST":
        email = request.POST.get("username")
        contrasena = request.POST.get("password")

        try:
            user = authenticate(request, username=email, password=contrasena)
            if user is not None:
                if not user.is_active:
                    messages.error(request, "Tu cuenta esta desactivada. Contacta al administrador.")
                    return redirect("effiadmi:login")

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
        total_productos = Product.objects.filter(activo=True).count()
        total_clientes = Cliente.objects.filter(activo=True).count()
        total_facturas = Factura.objects.filter(estado="emitida").count()
        total_pedidos = Pedido.objects.count()

        inventario = Inventory.objects.select_related("product").all()
        unidades_totales = inventario.aggregate(total=Sum("cantidad_disponible"))["total"] or 0
        valor_inventario = 0
        productos_bajo_stock = []

        for inv in inventario:
            valor_inventario += float(inv.product.precio_venta) * inv.cantidad_disponible
            if inv.cantidad_disponible <= inv.stock_minimo:
                productos_bajo_stock.append(inv)

        hoy = timezone.now().date()
        inicio_mes = hoy.replace(day=1)

        ventas_hoy = Factura.objects.filter(
            fecha_emision__date=hoy, estado="emitida"
        ).aggregate(total=Sum("total"))["total"] or 0
        ventas_mes = Factura.objects.filter(
            fecha_emision__date__gte=inicio_mes, estado="emitida"
        ).aggregate(total=Sum("total"))["total"] or 0

        productos_vendidos = (
            FacturaDetalle.objects
            .values(nombre=F("producto__nombre"))
            .annotate(total_vendido=Sum("cantidad"))
            .order_by("-total_vendido")[:5]
        )

        categorias_rentables = (
            FacturaDetalle.objects
            .values(nombre=F("producto__categoria__nombre"))
            .annotate(total=Sum("subtotal"))
            .order_by("-total")
            .exclude(nombre__isnull=True)
            .exclude(nombre="")
        )

        categorias_labels = []
        categorias_data = []
        for cat in categorias_rentables[:4]:
            categorias_labels.append(cat["nombre"])
            categorias_data.append(float(cat["total"]))

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
            "ventas_hoy": ventas_hoy,
            "ventas_mes": ventas_mes,
            "productos_vendidos": list(productos_vendidos),
            "categorias_labels": categorias_labels,
            "categorias_data": categorias_data,
            "productos_bajo_stock": productos_bajo_stock,
            "movimientos_recientes": movimientos_recientes,
        }
        return render(request, "dashboard/index.html", contexto)
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return render(request, "dashboard/index.html")


@autorizacion(roles=['admin', 'operador'])
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

    ctx = {"usuario": user, "perfil": perfil}
    if perfil.cargo == "admin":
        ctx["usuarios"] = User.objects.select_related("profile").all().order_by("-id")
    return render(request, "usuarios/perfil.html", ctx)


# ==================== CLIENTES ====================

@autorizacion(roles=['admin', 'operador'])
def lista_clientes(request):
    try:
        clientes_registrados = Cliente.objects.all().order_by("-id")
        return render(request, "clientes/lista_clientes.html", {"clientes": clientes_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=['admin', 'operador'])
def crear_cliente(request):
    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre", "").strip()
            correo = request.POST.get("correo", "").strip()
            telefono = request.POST.get("telefono", "").strip()
            direccion = request.POST.get("direccion", "").strip()

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


@autorizacion(roles=['admin'])
def editar_cliente(request, id):
    try:
        cliente = get_object_or_404(Cliente, pk=id)

        if request.method == "POST":
            cliente.nombre = request.POST.get("nombre", "").strip()
            cliente.correo = request.POST.get("correo", "").strip()
            cliente.telefono = request.POST.get("telefono", "").strip()
            cliente.direccion = request.POST.get("direccion", "").strip()
            cliente.save()
            messages.success(request, "¡Cliente actualizado exitosamente!")
            return redirect("effiadmi:lista_clientes")

        return render(request, "clientes/formulario_clientes.html", {"cliente": cliente})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_clientes")


@autorizacion(roles=['admin'])
def eliminar_cliente(request, id):
    try:
        cliente = get_object_or_404(Cliente, pk=id)
        if request.method == "POST":
            if cliente.activo:
                cliente.activo = False
                cliente.save()
                messages.success(request, "Cliente desactivado exitosamente.")
            else:
                cliente.activo = True
                cliente.save()
                messages.success(request, "Cliente activado exitosamente.")
        return redirect("effiadmi:lista_clientes")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_clientes")


# ==================== PRODUCTOS ====================

@autorizacion(roles=['admin', 'operador'])
def lista_productos(request):
    try:
        mostrar_inactivos = request.GET.get("inactivos") == "1"
        if mostrar_inactivos:
            productos_registrados = Product.objects.all().order_by("-id")
        else:
            productos_registrados = Product.objects.filter(activo=True).order_by("-id")

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


def _siguiente_id_producto():
    maximo = 0
    for sku in Product.objects.values_list("sku", flat=True):
        if str(sku).isdigit():
            maximo = max(maximo, int(sku))
    return str(maximo + 1)


@autorizacion(roles=['admin'])
def crear_producto(request):
    sucursales = Branch.objects.all()
    categorias = Categoria.objects.filter(activa=True).order_by("nombre")
    proximo_id = _siguiente_id_producto()
    _ctx = {"sucursales": sucursales, "categorias": categorias, "proximo_id": proximo_id}

    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre", "").strip()
            descripcion = request.POST.get("descripcion", "").strip()
            categoria_id = request.POST.get("categoria", "")
            precio_venta_str = request.POST.get("precio_venta", "0")
            sucursal_id = request.POST.get("sucursal")
            stock_inicial_str = request.POST.get("stock_inicial", "0")
            stock_minimo_str = request.POST.get("stock_minimo", "5")

            if not all([nombre, precio_venta_str]):
                messages.error(request, "Por favor completa los campos obligatorios.")
                return render(request, "productos/crear.html", _ctx)

            categoria = (
                Categoria.objects.filter(id=categoria_id, activa=True).first()
                if categoria_id else None
            )
            if not categoria:
                messages.error(request, "Debes seleccionar una categoria valida.")
                return render(request, "productos/crear.html", _ctx)

            try:
                precio_venta = Decimal(precio_venta_str)
            except (TypeError, ValueError):
                messages.error(request, "El precio de venta no es valido.")
                return render(request, "productos/crear.html", _ctx)

            if precio_venta <= 0:
                messages.error(request, "El precio de venta debe ser mayor a 0.")
                return render(request, "productos/crear.html", _ctx)

            if precio_venta != precio_venta.to_integral_value():
                messages.error(request, "El precio debe ser un valor entero en pesos colombianos, sin decimales.")
                return render(request, "productos/crear.html", _ctx)

            if precio_venta < 1000 or precio_venta > 100000000:
                messages.error(request, "El precio de venta debe estar entre $1.000 y $100.000.000 (pesos colombianos).")
                return render(request, "productos/crear.html", _ctx)

            precio_venta = int(precio_venta)

            try:
                stock_inicial = int(stock_inicial_str)
            except (TypeError, ValueError):
                stock_inicial = 0

            try:
                stock_minimo = int(stock_minimo_str)
            except (TypeError, ValueError):
                stock_minimo = 5

            if stock_inicial < 0:
                messages.error(request, "El stock inicial no puede ser negativo.")
                return render(request, "productos/crear.html", _ctx)

            if stock_minimo < 0:
                messages.error(request, "El stock minimo no puede ser negativo.")
                return render(request, "productos/crear.html", _ctx)

            branch = None
            if sucursal_id:
                branch = Branch.objects.filter(id=sucursal_id).first()
            if not branch:
                branch = Branch.objects.filter(es_principal=True).first()
            if not branch:
                branch = Branch.objects.create(nombre="Sucursal Principal", es_principal=True)

            with transaction.atomic():
                producto = Product.objects.create(
                    sku=proximo_id,
                    nombre=nombre,
                    descripcion=descripcion,
                    categoria=categoria,
                    precio_venta=precio_venta,
                )

                inventario = Inventory.objects.create(
                    product=producto,
                    branch=branch,
                    cantidad_disponible=stock_inicial,
                    stock_minimo=stock_minimo,
                )

                if stock_inicial > 0:
                    usuario = None
                    if request.session.get("logueado"):
                        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()
                    InventoryLog.objects.create(
                        inventory=inventario,
                        tipo_movimiento="ENTRADA",
                        cantidad=stock_inicial,
                        cantidad_resultante=stock_inicial,
                        motivo="Creacion automatica de producto con stock inicial",
                        usuario=usuario,
                    )

            messages.success(request, "¡Producto creado exitosamente!")
            return redirect("effiadmi:lista_productos")
        except IntegrityError:
            messages.error(request, "El SKU ya esta registrado.")
            return render(request, "productos/crear.html", _ctx)
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "productos/crear.html", _ctx)

    return render(request, "productos/crear.html", _ctx)


@autorizacion(roles=['admin'])
def editar_producto(request, id):
    try:
        producto = get_object_or_404(Product, pk=id)
        sucursales = Branch.objects.all()
        categorias = Categoria.objects.filter(activa=True).order_by("nombre")
        _ctx = {"producto": producto, "sucursales": sucursales, "categorias": categorias}

        if request.method == "POST":
            sku = request.POST.get("sku", "").strip()
            nombre = request.POST.get("nombre", "").strip()

            if not sku or not nombre:
                messages.error(request, "SKU y nombre son obligatorios.")
                return render(request, "productos/editar.html", _ctx)

            if not sku.isdigit():
                messages.error(request, "El ID del producto debe contener solo numeros.")
                return render(request, "productos/editar.html", _ctx)

            precio_venta_str = request.POST.get("precio_venta", "0")
            try:
                precio_venta = Decimal(precio_venta_str)
            except (TypeError, ValueError):
                messages.error(request, "El precio de venta no es valido.")
                return render(request, "productos/editar.html", _ctx)

            if precio_venta <= 0:
                messages.error(request, "El precio de venta debe ser mayor a 0.")
                return render(request, "productos/editar.html", _ctx)

            if precio_venta != precio_venta.to_integral_value():
                messages.error(request, "El precio debe ser un valor entero en pesos colombianos, sin decimales.")
                return render(request, "productos/editar.html", _ctx)

            if precio_venta < 1000 or precio_venta > 100000000:
                messages.error(request, "El precio de venta debe estar entre $1.000 y $100.000.000 (pesos colombianos).")
                return render(request, "productos/editar.html", _ctx)

            precio_venta = int(precio_venta)

            categoria_id = request.POST.get("categoria", "")
            if categoria_id:
                categoria = Categoria.objects.filter(id=categoria_id, activa=True).first()
                if not categoria:
                    messages.error(request, "La categoria seleccionada no es valida.")
                    return render(request, "productos/editar.html", _ctx)
            else:
                categoria = None

            producto.sku = sku
            producto.nombre = nombre
            producto.descripcion = request.POST.get("descripcion", "")
            producto.categoria = categoria
            producto.precio_venta = precio_venta
            producto.save()
            messages.success(request, "¡Producto actualizado exitosamente!")
            return redirect("effiadmi:lista_productos")

        return render(request, "productos/editar.html", _ctx)
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_productos")


@autorizacion(roles=['admin'])
def eliminar_producto(request, id):
    try:
        producto = get_object_or_404(Product, pk=id)
        if request.method == "POST":
            if not producto.activo:
                producto.activo = True
                producto.save()
                messages.success(request, "Producto activado exitosamente.")
                return redirect("effiadmi:lista_productos")

            tiene_historial = (
                Inventory.objects.filter(product=producto, cantidad_disponible__gt=0).exists()
                or PedidoDetalle.objects.filter(producto=producto).exists()
                or FacturaDetalle.objects.filter(producto=producto).exists()
                or ProveedorProducto.objects.filter(producto=producto).exists()
            )
            if tiene_historial:
                producto.activo = False
                producto.save()
                messages.warning(
                    request,
                    "El producto tiene registros asociados (inventario, pedidos, facturas o proveedores), "
                    "por lo que no se elimino. Quedo desactivado."
                )
            else:
                producto.delete()
                messages.success(request, "Producto eliminado exitosamente.")
        return redirect("effiadmi:lista_productos")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_productos")


# ==================== CATEGORIAS ====================

@autorizacion(roles=['admin'])
def lista_categorias(request):
    try:
        categorias_registradas = Categoria.objects.annotate(
            total_productos=Count("productos")
        ).order_by("nombre")
        return render(request, "categorias/lista.html", {"categorias": categorias_registradas})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=['admin'])
def crear_categoria(request):
    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre", "").strip().upper()
            if not nombre:
                messages.error(request, "Por favor escribe el nombre de la categoria.")
                return render(request, "categorias/crear.html")

            if Categoria.objects.filter(nombre__iexact=nombre).exists():
                messages.error(request, "El nombre de la categoria ya existe.")
                return render(request, "categorias/crear.html")

            Categoria.objects.create(nombre=nombre)
            messages.success(request, "¡Categoria creada exitosamente!")
            return redirect("effiadmi:lista_categorias")
        except IntegrityError:
            messages.error(request, "El nombre de la categoria ya existe.")
            return render(request, "categorias/crear.html")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return render(request, "categorias/crear.html")

    return render(request, "categorias/crear.html")


@autorizacion(roles=['admin'])
def editar_categoria(request, id):
    try:
        categoria = get_object_or_404(Categoria, pk=id)

        if request.method == "POST":
            nombre = request.POST.get("nombre", "").strip().upper()
            if not nombre:
                messages.error(request, "El nombre no puede estar vacio.")
                return render(request, "categorias/editar.html", {"categoria": categoria})

            existe = Categoria.objects.filter(nombre__iexact=nombre).exclude(pk=categoria.pk).exists()
            if existe:
                messages.error(request, "El nombre de la categoria ya existe.")
                return render(request, "categorias/editar.html", {"categoria": categoria})

            categoria.nombre = nombre
            categoria.save()
            messages.success(request, "¡Categoria actualizada exitosamente!")
            return redirect("effiadmi:lista_categorias")

        return render(request, "categorias/editar.html", {"categoria": categoria})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_categorias")


@autorizacion(roles=['admin'])
def eliminar_categoria(request, id):
    try:
        categoria = get_object_or_404(Categoria, pk=id)
        if request.method == "POST":
            tiene_productos = Product.objects.filter(categoria=categoria).exists()
            if tiene_productos:
                messages.error(
                    request,
                    "No se puede eliminar: hay productos asignados a esta categoria. "
                    "Reasigna los productos a otra categoria primero."
                )
                return redirect("effiadmi:lista_categorias")
            categoria.delete()
            messages.success(request, "Categoria eliminada exitosamente.")
        return redirect("effiadmi:lista_categorias")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_categorias")


# ==================== INVENTARIO ====================

@autorizacion(roles=['admin', 'operador'])
def lista_inventario(request):
    try:
        sucursal_id = request.GET.get("sucursal")
        categoria = request.GET.get("categoria")

        inventario = Inventory.objects.select_related("product", "branch").all()

        if sucursal_id:
            inventario = inventario.filter(branch_id=sucursal_id)
        if categoria:
            inventario = inventario.filter(product__categoria_id=categoria)

        inventario = inventario.order_by("product__categoria__nombre", "product__nombre")

        sucursales = Branch.objects.all()
        categorias = Categoria.objects.filter(activa=True).order_by("nombre")

        contexto = {
            "inventario": inventario,
            "sucursales": sucursales,
            "categorias": categorias,
            "sucursal_seleccionada": sucursal_id,
            "categoria_seleccionada": categoria,
        }
        return render(request, "inventario/lista.html", contexto)
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=['admin', 'operador'])
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


@autorizacion(roles=['admin', 'operador'])
def registrar_movimiento(request, id):
    try:
        inventario = get_object_or_404(
            Inventory.objects.select_related("product", "branch"), pk=id
        )

        if request.method == "POST":
            tipo = request.POST.get("tipo_movimiento")
            cantidad_str = request.POST.get("cantidad", "0")
            motivo = request.POST.get("motivo", "").strip()

            try:
                cantidad = int(cantidad_str)
            except (TypeError, ValueError):
                messages.error(request, "La cantidad no es valida.")
                return redirect("effiadmi:registrar_movimiento", id=inventario.id)

            if cantidad <= 0:
                messages.error(request, "La cantidad debe ser mayor a 0.")
                return redirect("effiadmi:registrar_movimiento", id=inventario.id)

            with transaction.atomic():
                if tipo == "ENTRADA":
                    inventario.cantidad_disponible += cantidad
                elif tipo == "SALIDA":
                    if inventario.cantidad_disponible < cantidad:
                        messages.error(
                            request,
                            f"Stock insuficiente. Disponible: {inventario.cantidad_disponible}, solicitado: {cantidad}"
                        )
                        return redirect("effiadmi:registrar_movimiento", id=inventario.id)
                    inventario.cantidad_disponible -= cantidad
                elif tipo == "AJUSTE":
                    if cantidad < 0:
                        messages.error(request, "La cantidad de ajuste no puede ser negativa.")
                        return redirect("effiadmi:registrar_movimiento", id=inventario.id)
                    inventario.cantidad_disponible = cantidad
                else:
                    messages.error(request, "Tipo de movimiento no valido.")
                    return redirect("effiadmi:registrar_movimiento", id=inventario.id)

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
                _notificar_stock_bajo(inventario)
                messages.warning(
                    request,
                    f"¡Alerta! Stock bajo para '{inventario.product.nombre}' "
                    f"({inventario.cantidad_disponible}/{inventario.stock_minimo})"
                )

            messages.success(request, f"¡{tipo} registrada exitosamente!")
            return redirect("effiadmi:detalle_inventario", id=inventario.id)

        return render(request, "inventario/movimientos.html", {"inventario": inventario})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_inventario")


# ==================== PEDIDOS ====================

@autorizacion(roles=['admin', 'operador'])
def lista_pedidos(request):
    try:
        pedidos_registrados = Pedido.objects.select_related("cliente").all().order_by("-id")
        return render(request, "pedidos/lista.html", {"pedidos": pedidos_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=['admin', 'operador'])
def crear_pedido(request):
    try:
        clientes_activos = Cliente.objects.filter(activo=True).order_by("nombre")
        productos_activos = list(Product.objects.filter(activo=True).order_by("nombre").values("id", "nombre", "precio_venta"))

        if request.method == "POST":
            cliente_id = request.POST.get("cliente")
            productos_ids = request.POST.getlist("producto")
            cantidades = request.POST.getlist("cantidad")

            if not cliente_id:
                messages.error(request, "Debes seleccionar un cliente.")
                return render(request, "pedidos/crear.html", {
                    "clientes": clientes_activos, "productos": productos_activos
                })

            cliente = get_object_or_404(Cliente, pk=cliente_id, activo=True)

            if not productos_ids or len(productos_ids) == 0:
                messages.error(request, "Debes agregar al menos un producto.")
                return render(request, "pedidos/crear.html", {
                    "clientes": clientes_activos, "productos": productos_activos
                })

            usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()

            with transaction.atomic():
                pedido = Pedido.objects.create(
                    cliente=cliente,
                    usuario=usuario,
                    estado="pendiente",
                    total=0,
                )

                total = Decimal("0")
                for i in range(len(productos_ids)):
                    if not productos_ids[i]:
                        continue
                    producto = Product.objects.get(pk=productos_ids[i], activo=True)
                    try:
                        cantidad = int(cantidades[i])
                    except (TypeError, ValueError, IndexError):
                        cantidad = 0

                    if cantidad <= 0:
                        messages.error(request, f"La cantidad para '{producto.nombre}' debe ser mayor a 0.")
                        pedido.delete()
                        return render(request, "pedidos/crear.html", {
                            "clientes": clientes_activos, "productos": productos_activos
                        })

                    precio = producto.precio_venta
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

            nombre_usuario = f"{usuario.first_name} {usuario.last_name}".strip() or usuario.username
            crear_notificacion(
                ids_admins(),
                f"Nuevo pedido #{pedido.id} de {cliente.nombre} (creado por {nombre_usuario}).",
                enlace=f"pedidos/{pedido.id}/",
            )

            messages.success(request, "¡Pedido creado exitosamente!")
            return redirect("effiadmi:lista_pedidos")

        return render(request, "pedidos/crear.html", {
            "clientes": clientes_activos, "productos": productos_activos
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion(roles=['admin', 'operador'])
def detalle_pedido(request, id):
    try:
        pedido = get_object_or_404(
            Pedido.objects.select_related("cliente", "usuario"), pk=id
        )
        detalles = PedidoDetalle.objects.filter(pedido=pedido).select_related("producto")
        factura = Factura.objects.filter(pedido=pedido).first()
        return render(request, "pedidos/detalle.html", {
            "pedido": pedido, "detalles": detalles, "factura_asociada": factura
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion(roles=['admin', 'operador'])
def confirmar_pedido(request, id):
    try:
        pedido = get_object_or_404(Pedido, pk=id)

        if request.method != "POST":
            return redirect("effiadmi:detalle_pedido", id=pedido.id)

        if pedido.estado != "pendiente":
            messages.warning(request, "Solo se pueden confirmar pedidos pendientes.")
            return redirect("effiadmi:detalle_pedido", id=pedido.id)

        detalles = PedidoDetalle.objects.filter(pedido=pedido).select_related("producto")

        if not detalles.exists():
            messages.error(request, "El pedido no tiene productos.")
            return redirect("effiadmi:detalle_pedido", id=pedido.id)

        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()
        branch = Branch.objects.filter(es_principal=True).first()
        if not branch:
            branch = Branch.objects.first()
        if not branch:
            messages.error(request, "No hay sucursales configuradas.")
            return redirect("effiadmi:detalle_pedido", id=pedido.id)

        with transaction.atomic():
            for det in detalles:
                inv = Inventory.objects.filter(
                    product=det.producto, branch=branch
                ).first()
                if not inv:
                    messages.error(
                        request,
                        f"No hay inventario para '{det.producto.nombre}' en {branch.nombre}."
                    )
                    return redirect("effiadmi:detalle_pedido", id=pedido.id)

                if inv.cantidad_disponible < det.cantidad:
                    messages.error(
                        request,
                        f"Stock insuficiente para '{det.producto.nombre}'. "
                        f"Disponible: {inv.cantidad_disponible}, requerido: {det.cantidad}."
                    )
                    return redirect("effiadmi:detalle_pedido", id=pedido.id)

            for det in detalles:
                inv = Inventory.objects.select_for_update().get(
                    product=det.producto, branch=branch
                )
                inv.cantidad_disponible -= det.cantidad
                inv.save()

                InventoryLog.objects.create(
                    inventory=inv,
                    tipo_movimiento="SALIDA",
                    cantidad=det.cantidad,
                    cantidad_resultante=inv.cantidad_disponible,
                    motivo=f"Salida por confirmacion de Pedido #{pedido.id}",
                    usuario=usuario,
                )
                if inv.cantidad_disponible <= inv.stock_minimo:
                    _notificar_stock_bajo(inv)

            pedido.estado = "confirmado"
            pedido.save()

        crear_notificacion(
            ids_admins(),
            f"Pedido #{pedido.id} confirmado. Stock descontado.",
            enlace=f"pedidos/{pedido.id}/",
        )
        messages.success(
            request,
            f"Pedido #{pedido.id} confirmado. Stock descontado."
        )
        return redirect("effiadmi:detalle_pedido", id=pedido.id)

    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion(roles=['admin', 'operador'])
def cancelar_pedido(request, id):
    try:
        pedido = get_object_or_404(Pedido, pk=id)

        if request.method != "POST":
            return redirect("effiadmi:detalle_pedido", id=pedido.id)

        if pedido.estado == "cancelado":
            messages.warning(request, "El pedido ya esta cancelado.")
            return redirect("effiadmi:detalle_pedido", id=pedido.id)

        with transaction.atomic():
            pedido.estado = "cancelado"
            pedido.save()

            factura = Factura.objects.filter(pedido=pedido, estado="emitida").first()
            if factura:
                factura.estado = "anulada"
                factura.save()

            detalles = PedidoDetalle.objects.filter(pedido=pedido).select_related("producto")
            for det in detalles:
                inv = Inventory.objects.filter(
                    product=det.producto
                ).first()
                if inv:
                    inv.cantidad_disponible += det.cantidad
                    inv.save()
                    usuario = None
                    if request.session.get("logueado"):
                        usuario = User.objects.filter(
                            id=request.session["logueado"]["id"]
                        ).first()
                    InventoryLog.objects.create(
                        inventory=inv,
                        tipo_movimiento="ENTRADA",
                        cantidad=det.cantidad,
                        cantidad_resultante=inv.cantidad_disponible,
                        motivo=f"Devolucion por cancelacion de Pedido #{pedido.id}",
                        usuario=usuario,
                    )

        crear_notificacion(
            ids_admins(),
            f"Pedido #{pedido.id} cancelado. Stock devuelto al inventario.",
            enlace=f"pedidos/{pedido.id}/",
        )
        messages.success(request, f"Pedido #{pedido.id} cancelado.")
        return redirect("effiadmi:detalle_pedido", id=pedido.id)

    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion(roles=['admin'])
def eliminar_pedido(request, id):
    try:
        pedido = get_object_or_404(Pedido, pk=id)
        if request.method == "POST":
            if pedido.estado == "pendiente":
                pedido.delete()
                messages.success(request, "¡Pedido eliminado exitosamente!")
            else:
                messages.warning(request, "Solo se pueden eliminar pedidos pendientes.")
        return redirect("effiadmi:lista_pedidos")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion(roles=['admin', 'operador'])
def editar_pedido(request, id):
    messages.warning(request, "Los pedidos se confirman o cancelan, no se editan.")
    return redirect("effiadmi:detalle_pedido", id=id)


@autorizacion(roles=['admin', 'operador'])
def pagar_pedido(request, id):
    try:
        pedido = get_object_or_404(Pedido, pk=id)

        if request.method != "POST":
            return redirect("effiadmi:detalle_pedido", id=pedido.id)

        if pedido.estado != "confirmado":
            messages.warning(request, "Solo se pueden pagar pedidos confirmados.")
            return redirect("effiadmi:detalle_pedido", id=pedido.id)

        if Factura.objects.filter(pedido=pedido, estado="emitida").exists():
            messages.warning(request, "Este pedido ya tiene una factura emitida.")
            return redirect("effiadmi:detalle_pedido", id=pedido.id)

        detalles = PedidoDetalle.objects.filter(pedido=pedido).select_related("producto")
        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()

        with transaction.atomic():
            factura = Factura.objects.create(
                cliente=pedido.cliente,
                usuario=usuario,
                pedido=pedido,
                total=pedido.total,
                estado="emitida",
            )

            for det in detalles:
                FacturaDetalle.objects.create(
                    factura=factura,
                    producto=det.producto,
                    cantidad=det.cantidad,
                    precio_unitario=det.precio_unitario,
                    subtotal=det.subtotal,
                )

            pedido.estado = "pagado"
            pedido.save()

        crear_notificacion(
            ids_admins(),
            f"Pedido #{pedido.id} pagado. Factura #{factura.id} generada.",
            enlace=f"facturas/{factura.id}/",
        )
        messages.success(
            request,
            f"Pedido #{pedido.id} marcado como pagado. Factura #{factura.id} generada."
        )
        return redirect("effiadmi:detalle_pedido", id=pedido.id)

    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


# ==================== FACTURAS ====================

@autorizacion(roles=['admin', 'operador'])
def lista_facturas(request):
    try:
        estado = request.GET.get("estado", "")
        facturas_registradas = Factura.objects.select_related(
            "cliente", "pedido"
        ).all().order_by("-id")
        if estado == "emitida":
            facturas_registradas = facturas_registradas.filter(estado="emitida")
        elif estado == "anulada":
            facturas_registradas = facturas_registradas.filter(estado="anulada")
        return render(request, "facturas/lista.html", {
            "facturas": facturas_registradas,
            "filtro_estado": estado,
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=['admin', 'operador'])
def detalle_factura(request, id):
    try:
        factura = get_object_or_404(
            Factura.objects.select_related("cliente", "usuario", "pedido"), pk=id
        )
        detalles = FacturaDetalle.objects.filter(factura=factura).select_related("producto")
        return render(request, "facturas/detalle.html", {
            "factura": factura, "detalles": detalles
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion(roles=['admin'])
def anular_factura(request, id):
    try:
        factura = get_object_or_404(Factura, pk=id)

        if request.method != "POST":
            return redirect("effiadmi:detalle_factura", id=factura.id)

        if factura.estado == "anulada":
            messages.warning(request, "La factura ya esta anulada.")
            return redirect("effiadmi:detalle_factura", id=factura.id)

        with transaction.atomic():
            factura.estado = "anulada"
            factura.save()

        crear_notificacion(
            ids_admins(),
            f"Factura #{factura.id} anulada (cliente: {factura.cliente.nombre}).",
            enlace=f"facturas/{factura.id}/",
        )
        messages.success(request, f"Factura #{factura.id} anulada.")
        return redirect("effiadmi:detalle_factura", id=factura.id)

    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion(roles=['admin'])
def eliminar_factura(request, id):
    try:
        factura = get_object_or_404(Factura, pk=id)
        if request.method == "POST":
            if factura.estado == "emitida":
                factura.estado = "anulada"
                factura.save()
                messages.success(request, "Factura anulada.")
            else:
                messages.warning(request, "La factura ya esta anulada.")
        return redirect("effiadmi:lista_facturas")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion(roles=['admin'])
def editar_factura(request, id):
    messages.warning(request, "Las facturas emitidas no se pueden editar. Anule y genere una nueva.")
    return redirect("effiadmi:detalle_factura", id=id)


# ==================== USUARIOS ====================

@autorizacion(roles=['admin'])
def lista_usuarios(request):
    try:
        usuarios_registrados = User.objects.select_related("profile").all().order_by("-id")
        return render(request, "usuarios/lista.html", {"usuarios": usuarios_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=['admin'])
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


@autorizacion(roles=['admin'])
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


@autorizacion(roles=['admin'])
def eliminar_usuario(request, id):
    try:
        user = get_object_or_404(User, pk=id)
        if request.method == "POST":
            if user.id == request.session.get("logueado", {}).get("id"):
                messages.warning(request, "No puedes desactivar tu propia cuenta.")
                return redirect("effiadmi:lista_usuarios")

            if user.is_active:
                user.is_active = False
                user.save()
                messages.success(request, "¡Usuario desactivado exitosamente!")
            else:
                user.is_active = True
                user.save()
                messages.success(request, "¡Usuario activado exitosamente!")
        return redirect("effiadmi:lista_usuarios")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_usuarios")


# ==================== PROVEEDORES ====================

@autorizacion(roles=['admin', 'operador'])
def lista_proveedores(request):
    try:
        estado = request.GET.get("estado", "")
        proveedores_registrados = Proveedor.objects.all().order_by("-id")
        if estado == "activo":
            proveedores_registrados = proveedores_registrados.filter(activo=True)
        elif estado == "inactivo":
            proveedores_registrados = proveedores_registrados.filter(activo=False)
        return render(request, "proveedores/lista.html", {
            "proveedores": proveedores_registrados,
            "filtro_estado": estado,
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=['admin'])
def crear_proveedor(request):
    if request.method == "POST":
        try:
            nombre = request.POST.get("nombre_proveedor", "").strip()
            correo = request.POST.get("correo", "").strip()
            telefono = request.POST.get("telefono", "").strip()
            direccion = request.POST.get("direccion", "").strip()

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


@autorizacion(roles=['admin'])
def editar_proveedor(request, id):
    try:
        proveedor = get_object_or_404(Proveedor, pk=id)

        if request.method == "POST":
            proveedor.nombre = request.POST.get("nombre_proveedor", "").strip()
            proveedor.correo = request.POST.get("correo", "").strip()
            proveedor.telefono = request.POST.get("telefono", "").strip()
            proveedor.direccion = request.POST.get("direccion", "").strip()
            proveedor.save()
            messages.success(request, "¡Proveedor actualizado exitosamente!")
            return redirect("effiadmi:lista_proveedores")

        return render(request, "proveedores/editar.html", {"proveedor": proveedor})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_proveedores")


@autorizacion(roles=['admin'])
def eliminar_proveedor(request, id):
    try:
        proveedor = get_object_or_404(Proveedor, pk=id)
        if request.method == "POST":
            if proveedor.activo:
                proveedor.activo = False
                proveedor.save()
                messages.success(request, "Proveedor desactivado exitosamente.")
            else:
                proveedor.activo = True
                proveedor.save()
                messages.success(request, "Proveedor activado exitosamente.")
        return redirect("effiadmi:lista_proveedores")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_proveedores")


# ==================== NOTIFICACIONES ====================

def _notificar_stock_bajo(inventario):
    mensaje = (
        f"ALERTA: Stock bajo para '{inventario.product.nombre}' "
        f"({inventario.cantidad_disponible}/{inventario.stock_minimo})."
    )
    ya_notificado = Notificacion.objects.filter(
        usuario_id__in=ids_admins(),
        mensaje=mensaje,
        leido=False,
    ).exists()
    if ya_notificado:
        return
    crear_notificacion(
        ids_admins(),
        mensaje,
        enlace=f"inventario/{inventario.id}/",
    )


@autorizacion(roles=['admin', 'operador'])
def lista_notificaciones(request):
    try:
        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()
        notificaciones_registradas = Notificacion.objects.filter(usuario=usuario).order_by("-id")
        return render(request, "notificaciones/lista.html", {"notificaciones": notificaciones_registradas})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=['admin', 'operador'])
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


@autorizacion(roles=['admin', 'operador'])
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


@autorizacion(roles=['admin', 'operador'])
def marcar_todas_leidas(request):
    try:
        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()
        Notificacion.objects.filter(usuario=usuario, leido=False).update(leido=True)
        messages.success(request, "Todas las notificaciones marcadas como leidas.")
        return redirect("effiadmi:lista_notificaciones")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_notificaciones")


# ==================== ESTADISTICAS IA ====================

@autorizacion(roles=['admin'])
def estadisticas_ia(request):
    try:
        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()
        es_admin = request.session["logueado"]["rol"] == "admin"

        total_productos = Product.objects.filter(activo=True).count()
        total_proveedores = Proveedor.objects.filter(activo=True).count()
        total_clientes = Cliente.objects.filter(activo=True).count()
        total_facturas = Factura.objects.filter(estado="emitida").count()

        inventario = Inventory.objects.all()
        unidades_totales = inventario.aggregate(total=Sum("cantidad_disponible"))["total"] or 0
        valor_inventario = 0
        productos_bajos = []

        precios_compra = {
            pp.producto_id: float(pp.precio_compra)
            for pp in ProveedorProducto.objects.select_related("producto")
        }
        proveedor_de = {}
        for pp in ProveedorProducto.objects.select_related("proveedor"):
            proveedor_de.setdefault(pp.producto_id, pp.proveedor.nombre)

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
            "total_usuarios": User.objects.filter(is_active=True).count(),
            "unidades_totales": unidades_totales,
            "valor_inventario": valor_inventario,
            "productos_bajos": productos_bajos,
            "producto_mas_vendido": producto_mas_vendido,
            "entradas": InventoryLog.objects.filter(tipo_movimiento="ENTRADA").count(),
            "salidas": InventoryLog.objects.filter(tipo_movimiento="SALIDA").count(),
            "es_admin": es_admin,
        }

        # Historial: admin ve todos (o filtra por usuario), operador ve solo el suyo
        usuarios_disponibles = []
        query_historial = ChatHistorial.objects.select_related("usuario")
        if es_admin:
            usuarios_disponibles = User.objects.filter(
                id__in=ChatHistorial.objects.values("usuario_id").distinct()
            ).order_by("username")
            filtro_usuario = request.GET.get("usuario", "")
            if filtro_usuario:
                query_historial = query_historial.filter(usuario_id=filtro_usuario)
        else:
            query_historial = query_historial.filter(usuario=usuario)
        contexto["historial"] = query_historial.order_by("-fecha")[:30]
        contexto["usuarios_disponibles"] = usuarios_disponibles

        # Contexto de negocio para la IA
        productos_str = []
        for v in ventas_por_producto[:15]:
            pid = v["producto__id"]
            margen = ""
            if pid in precios_compra:
                pv = {p.id: float(p.precio_venta) for p in Product.objects.filter(pk=pid)}
                if pid in pv:
                    margen = f", margen={round(pv[pid] - precios_compra[pid], 2)}"
            productos_str.append(
                f"{v['producto__nombre']}: {v['total']} uds vendidas{margen}"
            )
        bajos_str = []
        for inv in productos_bajos:
            prov = proveedor_de.get(inv.product_id, "sin proveedor asignado")
            bajos_str.append(
                f"{inv.product.nombre}: stock {inv.cantidad_disponible}/{inv.stock_minimo}, proveedor={prov}"
            )
        contexto_negocio = {
            "Productos activos": total_productos,
            "Proveedores": total_proveedores,
            "Clientes": total_clientes,
            "Facturas emitidas": total_facturas,
            "Valor del inventario": round(valor_inventario, 2),
            "Unidades totales en inventario": unidades_totales,
            "Ventas por producto": "; ".join(productos_str) if productos_str else "Sin ventas registradas",
            "Productos bajo stock": "; ".join(bajos_str) if bajos_str else "Ninguno",
            "Entradas de inventario": contexto["entradas"],
            "Salidas de inventario": contexto["salidas"],
        }

        if request.method == "POST":
            pregunta = request.POST.get("pregunta", "").strip()
            if pregunta:
                respuesta = consultar_asistente_effiadmi(pregunta, contexto_negocio=contexto_negocio)
                ChatHistorial.objects.create(
                    usuario=usuario,
                    mensaje=pregunta,
                    respuesta=respuesta,
                )
                contexto["respuesta_ia"] = respuesta
                contexto["pregunta"] = pregunta
            else:
                messages.warning(request, "Escribe una pregunta para el asistente IA.")

        return render(request, "dashboard/estadisticas.html", contexto)
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


# ==================== CHAT IA ====================

@autorizacion(roles=['admin'])
def chat_ia(request):
    return redirect("effiadmi:estadisticas_ia")


# ==================== REPORTES ====================

@autorizacion(roles=['admin', 'operador'])
def reportes(request):
    try:
        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()
        es_admin = request.session["logueado"]["rol"] == "admin"

        if es_admin:
            reportes_lista = Reporte.objects.select_related("usuario").all()
            filtro_estado = request.GET.get("estado", "")
            if filtro_estado:
                reportes_lista = reportes_lista.filter(estado=filtro_estado)
        else:
            reportes_lista = Reporte.objects.filter(usuario=usuario)

        if request.method == "POST":
            titulo = request.POST.get("titulo", "").strip()
            tipo = request.POST.get("tipo", "reporte_general")
            descripcion = request.POST.get("descripcion", "").strip()

            if not titulo or not descripcion:
                messages.error(request, "Debes completar el titulo y la descripcion.")
                return redirect("effiadmi:reportes")

            reporte = Reporte.objects.create(
                usuario=usuario,
                tipo=tipo,
                titulo=titulo,
                descripcion=descripcion,
            )
            nombre_operador = f"{usuario.first_name} {usuario.last_name}".strip() or usuario.username
            crear_notificacion(
                ids_admins(),
                f"Nuevo reporte de {nombre_operador}: {titulo}.",
                enlace=f"reportes/{reporte.id}/",
            )
            messages.success(request, "Reporte enviado exitosamente.")
            return redirect("effiadmi:reportes")

        return render(request, "dashboard/reportes.html", {
            "reportes": reportes_lista,
            "es_admin": es_admin,
            "filtro_estado": request.GET.get("estado", ""),
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=['admin', 'operador'])
def detalle_reporte(request, id):
    try:
        reporte = get_object_or_404(Reporte, pk=id)
        usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()
        es_admin = request.session["logueado"]["rol"] == "admin"

        if not es_admin and reporte.usuario != usuario:
            messages.warning(request, "No tienes acceso a este reporte.")
            return redirect("effiadmi:reportes")

        if request.method == "POST" and es_admin:
            respuesta = request.POST.get("respuesta", "").strip()
            nuevo_estado = request.POST.get("estado", reporte.estado)

            if respuesta:
                reporte.respuesta = respuesta
            reporte.estado = nuevo_estado
            reporte.fecha_respuesta = timezone.now()
            reporte.save()
            try:
                nombre_admin = f"{usuario.first_name} {usuario.last_name}".strip() or usuario.username
            except Exception:
                nombre_admin = "Administrador"
            crear_notificacion(
                [reporte.usuario_id],
                f"Tu reporte '{reporte.titulo}' fue respondido por {nombre_admin}.",
                enlace=f"reportes/{reporte.id}/",
            )
            messages.success(request, "Reporte actualizado exitosamente.")
            return redirect("effiadmi:detalle_reporte", id=reporte.id)

        if reporte.estado == "pendiente" and es_admin:
            reporte.estado = "visto"
            reporte.save()

        return render(request, "dashboard/detalle_reporte.html", {
            "reporte": reporte,
            "es_admin": es_admin,
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:reportes")


# ==================== BACKEND DE AUTENTICACION ====================


class EmailOrUsernameBackend:
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = User
        if username is None:
            username = kwargs.get("username")
        if username is None or password is None:
            return None

        from django.db.models import Q

        try:
            user = UserModel.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
