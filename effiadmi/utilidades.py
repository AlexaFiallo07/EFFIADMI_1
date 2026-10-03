from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def crear_notificacion(usuarios, mensaje, enlace=""):
    from .models import Notificacion, UserProfile

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


# Tipos de archivo admitidos al adjuntar una factura de compra. Un .html o un
# .svg subido se sirve desde /media/ y ejecutaria JavaScript en el origen de la
# app, asi que la lista es cerrada.
_MAGIC_ADJUNTOS = {
    ".pdf": b"%PDF",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".webp": b"RIFF",
}

TAMANIO_MAX_ADJUNTO = 10 * 1024 * 1024  # 10 MB


def _nombre_seguro(nombre):
    """Quita rutas y deja solo un nombre de archivo utilizable."""
    import os
    import re

    base = os.path.basename(nombre or "").strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    base = base.lstrip(".") or "archivo"
    return base[:100]


def validar_adjunto(archivo):
    """Valida un archivo subido. Devuelve (archivo, "") o (None, mensaje_de_error).

    El tipo se comprueba con los bytes magicos del archivo y no con
    request.FILES[...].content_type: ese valor lo elige el cliente y se puede
    falsificar sin dificultad.
    """
    import os

    if not archivo:
        return None, ""

    nombre = _nombre_seguro(archivo.name)
    ext = os.path.splitext(nombre)[1].lower()

    if ext not in _MAGIC_ADJUNTOS:
        permitidas = ", ".join(sorted(e.lstrip(".") for e in _MAGIC_ADJUNTOS))
        return None, (
            f"Tipo de archivo no permitido ({ext or 'sin extension'}). "
            f"Se admiten: {permitidas}."
        )

    if archivo.size > TAMANIO_MAX_ADJUNTO:
        mb = TAMANIO_MAX_ADJUNTO // (1024 * 1024)
        return None, f"El archivo supera el maximo permitido de {mb} MB."

    archivo.seek(0)
    cabecera = archivo.read(16)
    archivo.seek(0)

    if not cabecera.startswith(_MAGIC_ADJUNTOS[ext]):
        return None, "El contenido del archivo no coincide con su extension."

    if ext == ".webp" and cabecera[8:12] != b"WEBP":
        return None, "El contenido del archivo no coincide con su extension."

    return archivo, ""


def autorizacion(roles=[]):
    """Exige sesion y, ademas, que la cuenta siga activa con ese cargo en la BD.

    Antes solo se miraba request.session["logueado"], que es una copia del
    estado al hacer login: si a un usuario lo degradaban o desactivaban
    conservaba el acceso hasta que cerrara sesion. Aqui se relee la BD.
    """
    def verificar_autenticacion(func):
        @wraps(func)
        def envoltorio_func(request, *args, **kwargs):
            from django.contrib.auth.models import User

            validar = request.session.get("logueado", False)
            if not validar:
                return redirect("effiadmi:login")

            usuario = User.objects.filter(id=validar["id"]).first()
            if usuario is None or not usuario.is_active:
                # La cuenta fue borrada o desactivada despues del login:
                # se cierra la sesion para que no pueda volver a entrar.
                request.session.flush()
                messages.error(
                    request,
                    "Tu cuenta esta desactivada. Contacta al administrador.",
                )
                return redirect("effiadmi:login")

            cargo = usuario.profile.cargo if hasattr(usuario, "profile") else "operador"

            # La sesion guardaba un cargo distinto al actual: se sincroniza
            # antes de comprobar permisos, asi el resto de vistas (que leen la
            # sesion) no quedan desfasadas.
            if validar.get("rol") != cargo:
                request.session["logueado"]["rol"] = cargo
                request.session.modified = True

            if roles and cargo not in roles:
                messages.warning(request, "No tienes permisos para acceder a esta seccion.")
                return redirect("effiadmi:inicio")

            return func(request, *args, **kwargs)

        return envoltorio_func
    return verificar_autenticacion
