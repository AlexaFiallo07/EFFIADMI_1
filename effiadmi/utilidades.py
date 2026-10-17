from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from functools import wraps


def crear_notificacion(usuarios, mensaje, enlace=""):
    from .models import Notificacion
    if isinstance(usuarios, int):
        usuarios = [usuarios]
    if not usuarios:
        return []
    creadas = []
    for uid in usuarios:
        creadas.append(Notificacion.objects.create(usuario_id=uid, mensaje=mensaje, enlace=enlace))
    return creadas


def ids_admins():
    from django.contrib.auth.models import User
    return list(User.objects.filter(is_active=True, profile__cargo="admin").values_list("id", flat=True))


def notificaciones_no_leidas(request):
    from .models import Notificacion
    no_leidas = 0
    logueado = request.session.get("logueado")
    if logueado:
        no_leidas = Notificacion.objects.filter(usuario_id=logueado["id"], leido=False).count()
    return {"no_leidas_notificaciones": no_leidas}


def enviar_correo(destinatario, asunto, cuerpo, **kwargs):
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.contrib.staticfiles.templatetags.staticfiles import static

    try:
        request = kwargs.get("request")
        enlace = kwargs.get("enlace") or ""
        texto_enlace = kwargs.get("texto_enlace") or "Ver detalle"
        template = kwargs.get("template") or "emails/aviso.html"

        logo_url = ""
        if request:
            try:
                logo_url = request.build_absolute_uri(static("img/logoeffiadmi.png"))
            except Exception:
                logo_url = ""

        contexto = {
            "asunto": asunto,
            "cuerpo": cuerpo,
            "enlace": enlace,
            "texto_enlace": texto_enlace,
            "logo_url": logo_url,
            **(kwargs.get("contexto_extra") or {}),
        }

        html_content = render_to_string(template, contexto, request=request if request else None)
        text_content = cuerpo
        msg = EmailMultiAlternatives(asunto, text_content, settings.DEFAULT_FROM_EMAIL, [destinatario])
        msg.attach_alternative(html_content, "text/html")
        enviados = msg.send(fail_silently=False)
        return (True, "") if enviados else (False, "El servidor de correo no confirmó el envío.")
    except Exception as e:
        return False, str(e)


def enviar_correo_html(destinatario, asunto, cuerpo, **kwargs):
    return enviar_correo(destinatario, asunto, cuerpo, **kwargs)


def autorizacion(roles=[]):
    def verificar_autenticacion(func):
        @wraps(func)
        def envoltorio_func(request, *args, **kwargs):
            validar = request.session.get("logueado", False)
            if validar:
                try:
                    from django.contrib.auth.models import User
                    uid = validar.get("id")
                    user = User.objects.filter(id=uid, is_active=True).first()
                    if not user:
                        request.session.flush()
                        messages.error(request, "Tu cuenta no está activa o no existe.")
                        login_url = reverse("effiadmi:login")
                        return redirect(login_url)
                except Exception:
                    pass
                if roles and validar.get("rol") not in roles:
                    messages.warning(request, "No tienes permisos para acceder a esta sección.")
                    return redirect("effiadmi:inicio")
                return func(request, *args, **kwargs)
            else:
                login_url = reverse("effiadmi:login")
                return redirect(f"{login_url}?next={request.get_full_path()}")
        return envoltorio_func
    return verificar_autenticacion
