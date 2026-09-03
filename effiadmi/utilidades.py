from django.shortcuts import redirect
from django.contrib import messages


def crear_notificacion(usuarios, mensaje, enlace=""):
    from .models import Notificacion, UserProfile

    if isinstance(usuarios, (int, list)):
        pass
    if isinstance(usuarios, int):
        usuarios = [usuarios]
    if not usuarios:
        return []
    creadas = []
    for uid in usuarios:
        notif = Notificacion.objects.create(usuario_id=uid, mensaje=mensaje, enlace=enlace)
        creadas.append(notif)
    return creadas


def ids_admins():
    from django.contrib.auth.models import User

    return list(
        User.objects.filter(is_active=True, profile__cargo="admin").values_list("id", flat=True)
    )


def notificaciones_no_leidas(request):
    from .models import Notificacion

    no_leidas = 0
    logueado = request.session.get("logueado")
    if logueado:
        no_leidas = Notificacion.objects.filter(
            usuario_id=logueado["id"], leido=False
        ).count()
    return {"no_leidas_notificaciones": no_leidas}


def autorizacion(roles=[]):
    def verificar_autenticacion(func):
        def envoltorio_func(request, *args, **kwargs):
            # captura de variable de sesion
            validar = request.session.get("logueado", False)
            if validar:
                if roles != [] and validar["rol"] not in roles:
                    messages.warning(request, "No tienes permisos para acceder a esta seccion.")
                    return redirect("effiadmi:inicio")
                return func(request, *args, **kwargs)
            else:
                return redirect("effiadmi:login")

        return envoltorio_func
    return verificar_autenticacion
