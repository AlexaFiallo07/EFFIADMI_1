from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.db import IntegrityError, transaction
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
from .models import (
    UserProfile, Branch, Product, Inventory, InventoryLog,
    Cliente, Proveedor, ProveedorProducto,
    Factura, FacturaDetalle, Pedido, PedidoDetalle,
    Notificacion, ChatHistorial,
)
from .servicio_ia import consultar_asistente_effiadmi
from .utilidades import autorizacion


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
            .values(nombre=F("producto__categoria"))
            .annotate(total=Sum("subtotal"))
            .order_by("-total")
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


@autorizacion()
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


@autorizacion()
def eliminar_cliente(request, id):
    try:
        cliente = get_object_or_404(Cliente, pk=id)
        if request.method == "POST":
            cliente.activo = False
            cliente.save()
            messages.success(request, "Cliente desactivado exitosamente.")
        return redirect("effiadmi:lista_clientes")
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_clientes")


# ==================== PRODUCTOS ====================

@autorizacion()
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


@autorizacion()
def crear_producto(request):
    sucursales = Branch.objects.all()

    if request.method == "POST":
        try:
            sku = request.POST.get("sku", "").strip()
            nombre = request.POST.get("nombre", "").strip()
            descripcion = request.POST.get("descripcion", "").strip()
            categoria = request.POST.get("categoria", "").strip()
            precio_venta_str = request.POST.get("precio_venta", "0")
            sucursal_id = request.POST.get("sucursal")
            stock_inicial_str = request.POST.get("stock_inicial", "0")
            stock_minimo_str = request.POST.get("stock_minimo", "5")

            if not all([sku, nombre, precio_venta_str]):
                messages.error(request, "Por favor completa los campos obligatorios.")
                return render(request, "productos/crear.html", {"sucursales": sucursales})

            try:
                precio_venta = Decimal(precio_venta_str)
            except (TypeError, ValueError):
                messages.error(request, "El precio de venta no es valido.")
                return render(request, "productos/crear.html", {"sucursales": sucursales})

            if precio_venta <= 0:
                messages.error(request, "El precio de venta debe ser mayor a 0.")
                return render(request, "productos/crear.html", {"sucursales": sucursales})

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
                return render(request, "productos/crear.html", {"sucursales": sucursales})

            if stock_minimo < 0:
                messages.error(request, "El stock minimo no puede ser negativo.")
                return render(request, "productos/crear.html", {"sucursales": sucursales})

            branch = None
            if sucursal_id:
                branch = Branch.objects.filter(id=sucursal_id).first()
            if not branch:
                branch = Branch.objects.filter(es_principal=True).first()
            if not branch:
                branch = Branch.objects.create(nombre="Sucursal Principal", es_principal=True)

            with transaction.atomic():
                producto = Product.objects.create(
                    sku=sku,
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
            sku = request.POST.get("sku", "").strip()
            nombre = request.POST.get("nombre", "").strip()

            if not sku or not nombre:
                messages.error(request, "SKU y nombre son obligatorios.")
                return render(request, "productos/editar.html", {"producto": producto, "sucursales": sucursales})

            precio_venta_str = request.POST.get("precio_venta", "0")
            try:
                precio_venta = Decimal(precio_venta_str)
            except (TypeError, ValueError):
                messages.error(request, "El precio de venta no es valido.")
                return render(request, "productos/editar.html", {"producto": producto, "sucursales": sucursales})

            if precio_venta <= 0:
                messages.error(request, "El precio de venta debe ser mayor a 0.")
                return render(request, "productos/editar.html", {"producto": producto, "sucursales": sucursales})

            producto.sku = sku
            producto.nombre = nombre
            producto.descripcion = request.POST.get("descripcion", "")
            producto.categoria = request.POST.get("categoria", "")
            producto.precio_venta = precio_venta
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
            producto.activo = False
            producto.save()
            messages.success(request, "Producto desactivado exitosamente.")
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
        clientes_activos = Cliente.objects.filter(activo=True).order_by("nombre")
        productos_activos = Product.objects.filter(activo=True).order_by("nombre")

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

            messages.success(request, "¡Pedido creado exitosamente!")
            return redirect("effiadmi:lista_pedidos")

        return render(request, "pedidos/crear.html", {
            "clientes": clientes_activos, "productos": productos_activos
        })
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
        factura = Factura.objects.filter(pedido=pedido).first()
        return render(request, "pedidos/detalle.html", {
            "pedido": pedido, "detalles": detalles, "factura_asociada": factura
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion()
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

            pedido.estado = "confirmado"
            pedido.save()

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

        messages.success(
            request,
            f"Pedido #{pedido.id} confirmado. Factura #{factura.id} generada."
        )
        return redirect("effiadmi:detalle_pedido", id=pedido.id)

    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion()
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
                for det in FacturaDetalle.objects.filter(factura=factura):
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

        messages.success(request, f"Pedido #{pedido.id} cancelado.")
        return redirect("effiadmi:detalle_pedido", id=pedido.id)

    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_pedidos")


@autorizacion()
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


@autorizacion()
def editar_pedido(request, id):
    messages.warning(request, "Los pedidos se confirman o cancelan, no se editan.")
    return redirect("effiadmi:detalle_pedido", id=id)


# ==================== FACTURAS ====================

@autorizacion()
def lista_facturas(request):
    try:
        facturas_registradas = Factura.objects.select_related(
            "cliente", "pedido"
        ).all().order_by("-id")
        return render(request, "facturas/lista.html", {"facturas": facturas_registradas})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion()
def crear_factura(request):
    try:
        clientes_activos = Cliente.objects.filter(activo=True).order_by("nombre")
        productos_activos = Product.objects.filter(activo=True).order_by("nombre")

        if request.method == "POST":
            cliente_id = request.POST.get("cliente")
            productos_ids = request.POST.getlist("producto")
            cantidades = request.POST.getlist("cantidad")

            if not cliente_id:
                messages.error(request, "Debes seleccionar un cliente.")
                return render(request, "facturas/crear.html", {
                    "clientes": clientes_activos, "productos": productos_activos
                })

            cliente = get_object_or_404(Cliente, pk=cliente_id, activo=True)

            if not productos_ids or not any(productos_ids):
                messages.error(request, "Debes agregar al menos un producto.")
                return render(request, "facturas/crear.html", {
                    "clientes": clientes_activos, "productos": productos_activos
                })

            usuario = User.objects.filter(id=request.session["logueado"]["id"]).first()

            with transaction.atomic():
                factura = Factura.objects.create(
                    cliente=cliente,
                    usuario=usuario,
                    total=0,
                    estado="emitida",
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
                        continue

                    precio = producto.precio_venta
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

        return render(request, "facturas/crear.html", {
            "clientes": clientes_activos, "productos": productos_activos
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion()
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


@autorizacion()
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

        messages.success(request, f"Factura #{factura.id} anulada.")
        return redirect("effiadmi:detalle_factura", id=factura.id)

    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:lista_facturas")


@autorizacion()
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


@autorizacion()
def editar_factura(request, id):
    messages.warning(request, "Las facturas emitidas no se pueden editar. Anule y genere una nueva.")
    return redirect("effiadmi:detalle_factura", id=id)


# ==================== USUARIOS ====================

@autorizacion(roles=["admin"])
def lista_usuarios(request):
    try:
        usuarios_registrados = User.objects.select_related("profile").all().order_by("-id")
        return render(request, "usuarios/lista.html", {"usuarios": usuarios_registrados})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect("effiadmi:inicio")


@autorizacion(roles=["admin"])
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


@autorizacion(roles=["admin"])
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


@autorizacion(roles=["admin"])
def eliminar_usuario(request, id):
    try:
        user = get_object_or_404(User, pk=id)
        if request.method == "POST":
            if user.id == request.session.get("logueado", {}).get("id"):
                messages.warning(request, "No puedes desactivar tu propia cuenta.")
                return redirect("effiadmi:lista_usuarios")

            user.is_active = False
            user.save()
            messages.success(request, "¡Usuario desactivado exitosamente!")
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


@autorizacion()
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


@autorizacion()
def eliminar_proveedor(request, id):
    try:
        proveedor = get_object_or_404(Proveedor, pk=id)
        if request.method == "POST":
            proveedor.activo = False
            proveedor.save()
            messages.success(request, "Proveedor desactivado exitosamente.")
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



# ==================== ESTADISTICAS IA ====================

@autorizacion()
def estadisticas_ia(request):
    try:
        total_productos = Product.objects.filter(activo=True).count()
        total_proveedores = Proveedor.objects.filter(activo=True).count()
        total_clientes = Cliente.objects.filter(activo=True).count()
        total_facturas = Factura.objects.filter(estado="emitida").count()

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
            "total_usuarios": User.objects.filter(is_active=True).count(),
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
