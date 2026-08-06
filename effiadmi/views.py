from django.contrib import messages
from django.shortcuts import redirect, render

from .models import Clientes, Usuario
import functools


def autorizacion():
    """Simple authorization decorator that requires a logged-in session."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.session.get("logueado"):
                return redirect("effiadmi:login")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def login(request):
    if request.method == "POST":
        usuario = request.POST.get("username")
        contrasena = request.POST.get("password")

        try:
            u = Usuario.objects.get(email=usuario, contraseña=contrasena)
            messages.success(request, f"Bienvenido, {u.nombre_usuario}!")

            request.session["logueado"] = {
                "id": u.id,
                "nombre": f"{u.nombre_usuario}",
                "rol": u.cargo,
            }
            return redirect("effiadmi:inicio")
        except Usuario.DoesNotExist:
            messages.error(request, "Usuario o contrasena incorrectos...")
            request.session["logueado"] = None
            return redirect("effiadmi:login")

    if request.session.get("logueado", False):
        return redirect("effiadmi:inicio")
    return render(request, "usuarios/login.html")


@autorizacion()
def logout(request):
    try:
        del request.session["logueado"]
        messages.success(request, "Sesion cerrada exitosamente!")
        return redirect("effiadmi:login")
    except Exception as e:
        messages.warning(request, f"Error al cerrar sesion: {str(e)}")
        return redirect("effiadmi:inicio")


@autorizacion()
def inicio(request):
    return render(request, "dashboard/index.html")


@autorizacion()
def clientes(request):
    clientes_registrados = Clientes.objects.all()
    return render(request, "clientes/lista_clientes.html", {"clientes": clientes_registrados})


def inventario(request):
    return render(request, "inventario/lista.html")


def notificaciones(request):
    return render(request, "notificaciones/lista.html")


def pagos(request):
    return render(request, "pagos/lista.html")


def pedidos(request):
    return render(request, "pedidos/lista.html")


def productos(request):
    return render(request, "productos/lista.html")


def proveedores(request):
    return render(request, "proveedores/lista.html")


def facturas(request):
    return render(request, "facturas/lista.html")


def reportes(request):
    return render(request, "reportes/lista.html")


@autorizacion()
def usuarios(request):
    return render(request, "usuarios/lista.html")


@autorizacion()
def perfil(request):
    return render(request, "usuarios/perfil.html")


@autorizacion()
def crear_producto(request):
    return render(request, "productos/crear.html")


@autorizacion()
def crear_factura(request):
    return render(request, "facturas/crear.html")


@autorizacion()
def crear_pedido(request):
    return render(request, "pedidos/crear.html")


@autorizacion()
def lista_clientes(request):
    clientes_registrados = Clientes.objects.all()
    return render(request, "clientes/lista_clientes.html", {"clientes": clientes_registrados})


@autorizacion()
def formulario_clientes(request, id=None):
    datos = Clientes.objects.get(pk=id) if id else None

    if request.method == "POST":
        c = datos or Clientes()
        c.nombre = request.POST.get("nombre")
        c.correo = request.POST.get("correo")
        c.telefono = request.POST.get("telefono")
        c.direccion = request.POST.get("direccion")
        c.save()

        messages.success(request, "Cliente guardado exitosamente.")
        return redirect("effiadmi:lista_clientes")

    return render(request, "clientes/formulario_clientes.html", {"datos": datos})


@autorizacion()
def crear_cliente(request):
    if request.method == "POST":
        try:
            Clientes.objects.create(
                nombre=request.POST.get("nombre"),
                correo=request.POST.get("correo"),
                telefono=request.POST.get("telefono"),
                direccion=request.POST.get("direccion"),
            )
            messages.success(request, "Cliente creado exitosamente!")
            return redirect("effiadmi:lista_clientes")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return redirect("effiadmi:crear_cliente")

    return render(request, "clientes/formulario_clientes.html")
