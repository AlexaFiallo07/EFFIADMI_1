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


def _correo_configurado():
    from django.conf import settings

    return bool(getattr(settings, "EMAIL_HOST_USER", ""))


def _backend_es_consola():
    from django.conf import settings

    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    return "console" in backend.lower()


def enviar_correo(destinatario, asunto, cuerpo):
    """Envia un correo real usando la configuracion SMTP del .env.

    Devuelve (exitoso, mensaje_error).
    """
    from django.conf import settings
    from django.core.mail import send_mail

    if _backend_es_consola() or not _correo_configurado():
        return (
            False,
            "Modo prueba: el SMTP no esta configurado (falta EMAIL_HOST_USER y "
            "EMAIL_HOST_PASSWORD en el .env), por lo que el correo NO se envio. "
            "Con Gmail usa una contrasena de aplicacion (gratis) y luego se enviara de verdad.",
        )

    try:
        enviados = send_mail(
            asunto,
            cuerpo,
            settings.DEFAULT_FROM_EMAIL,
            [destinatario],
            fail_silently=False,
        )
        if enviados:
            return True, ""
        return False, "El servidor de correo no confirmo el envio."
    except Exception as e:
        return False, str(e)


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
