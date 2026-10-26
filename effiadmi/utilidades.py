import re
from functools import wraps

from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives


def crear_notificacion(usuarios, mensaje, enlace=""):
    from .models import Notificacion

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


def cargo_de_usuario(user):
    """Cargo actual del usuario en la BD ('admin' u 'operador'); '' si no hay perfil.

    Se lee en cada peticion (no de la sesion) para que un cambio de rol o una
    cuenta desactivada surta efecto de inmediato, igual que hace `autorizacion`.
    """
    from .models import UserProfile

    if not user or not user.is_authenticated:
        return ""
    return (
        UserProfile.objects.filter(user=user)
        .values_list("cargo", flat=True)
        .first()
        or ""
    )


def limite_alcanzado(clave, maximo, ventana):
    """Incrementa el contador de `clave` en cache y devuelve True si supero el maximo.

    Ventana en segundos. Usado para limitar envios de correo, el formulario
    publico de contacto y las consultas al chat IA sin depender de DRF.
    """
    from django.core.cache import cache

    try:
        intentos = cache.incr(clave)
    except ValueError:
        cache.set(clave, 1, ventana)
        intentos = 1
    return intentos > maximo


def notificaciones_no_leidas(request):
    from .models import Notificacion

    no_leidas = 0
    logueado = request.session.get("logueado")
    if logueado:
        no_leidas = Notificacion.objects.filter(
            usuario_id=logueado["id"], leido=False
        ).count()
    return {"no_leidas_notificaciones": no_leidas}


def assets_version(request):
    """Version para romper la cache de CSS/JS estaticos.

    Se calcula con la fecha de modificacion de las hojas de estilo y del JS
    principal. Al editar cualquiera de ellos la URL cambia (?v=...) y el
    navegador deja de reutilizar la copia antigua, sin que el usuario tenga
    que limpiar la cache ni recargar con Ctrl+F5.
    """
    from pathlib import Path

    from django.conf import settings

    base = Path(settings.BASE_DIR) / "static"
    version = 0
    for rel in (
        "css/styles.css",
        "css/wireframe.css",
        "css/estilos.css",
        "js/principal.js",
    ):
        try:
            version = max(version, int((base / rel).stat().st_mtime))
        except OSError:
            continue
    return {"assets_version": version}


def _correo_configurado():
    from django.conf import settings

    return bool(getattr(settings, "EMAIL_HOST_USER", ""))


def _backend_es_consola():
    from django.conf import settings

    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    return "console" in backend.lower()


class _CorreoConLogo(EmailMultiAlternatives):
    """Correo HTML con recursos inline (logo) en multipart/related.

    Gmail y Outlook solo renderizan <img src="cid:..."> si la imagen vive
    en un contenedor multipart/related; si queda en multipart/mixed la
    ignoran y el logo no aparece.
    """

    def _add_attachments(self, msg):
        import email.message
        from email.mime.base import MIMEBase

        if not self.attachments:
            return

        hay_inline = any(
            isinstance(a, (email.message.MIMEPart, MIMEBase)) and a.get("Content-ID")
            for a in self.attachments
        )
        if not hay_inline:
            return super()._add_attachments(msg)

        # Mover el contenido actual (multipart/alternative) a una subparte
        # y convertir la raiz en multipart/related (mismo patron que usa
        # email.message.EmailMessage._make_multipart).
        keep_headers = []
        part_headers = []
        for name, value in msg._headers:
            if name.lower().startswith("content-"):
                part_headers.append((name, value))
            else:
                keep_headers.append((name, value))

        alt = type(msg)(policy=msg.policy)
        alt._headers = part_headers
        alt._payload = msg._payload
        msg._payload = [alt]
        msg._headers = keep_headers
        msg["Content-Type"] = "multipart/related"

        for attachment in self.attachments:
            if isinstance(attachment, (email.message.MIMEPart, MIMEBase)):
                msg.attach(attachment)
            else:
                self._add_attachment(msg, *attachment)


def enviar_correo(destinatario, asunto, cuerpo, **kwargs):
    """Envia un correo con plantilla HTML usando la configuracion SMTP del .env.

    Devuelve (exitoso, mensaje_error).
    """
    from django.conf import settings
    from django.template.loader import render_to_string

    if _backend_es_consola() or not _correo_configurado():
        return (
            False,
            "Modo prueba: el SMTP no esta configurado (falta EMAIL_HOST_USER y "
            "EMAIL_HOST_PASSWORD en el .env), por lo que el correo NO se envio. "
            "Con Gmail usa una contrasena de aplicacion (gratis) y luego se enviara de verdad.",
        )

    try:
        request = kwargs.get("request")
        enlace = kwargs.get("enlace") or ""
        texto_enlace = kwargs.get("texto_enlace") or "Ver detalle"
        template = kwargs.get("template") or "emails/aviso.html"

        logo_url = "cid:effiadmi-logo"
        logo_adjunto = False
        try:
            from email.mime.image import MIMEImage
            from pathlib import Path as _Path
            _logo_path = _Path(settings.BASE_DIR) / "static" / "img" / "logoeffiadmi.png"
            if _logo_path.exists():
                _mime = MIMEImage(_logo_path.read_bytes(), name="logoeffiadmi.png")
                _mime.add_header("Content-ID", "<effiadmi-logo>")
                _mime.add_header("Content-Disposition", "inline", filename="logoeffiadmi.png")
                logo_adjunto = True
        except Exception:
            logo_url = ""
            _mime = None

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
        msg = _CorreoConLogo(asunto, text_content, settings.DEFAULT_FROM_EMAIL, [destinatario])
        msg.attach_alternative(html_content, "text/html")
        if logo_adjunto:
            msg.attach(_mime)
        enviados = msg.send(fail_silently=False)
        return (True, "") if enviados else (False, "El servidor de correo no confirmó el envío.")
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


_EXTENSIONES_CORREO = frozenset("""
com co net org edu gov mil int info biz name pro aero asia cat coop jobs mobi
museum post tel travel xxx
app dev io ai tech online site store shop blog cloud digital email live life
world today news media studio design art xyz top club vip link click website
space fun icu buzz monster quest rest bar cafe pizza fitness health care clinic
academy school university institute finance financial bank capital money market
markets business enterprise industries engineering construction contractors
realestate properties estate homes house land farm garden photo photography
pics video audio music band show theater tickets events vacations holidays
hotel hotels restaurant recipes food coffee wine beer organic green eco earth
energy solar water city town zone center community social team group family
friends love dating games game play toys kids baby wedding gifts deals discount
sale auction download stream tube chat wiki help support expert consulting
coach training education courses law legal attorney lawyer tax accountant
insurance doctor dentist hospital pharmacy dental vision yoga golf tennis soccer
football basketball baseball hockey cricket rugby fishing hunting camping
outdoors adventure tours cruises flights airline airport taxi cars auto
motorcycles boats yachts trucks parts repair tools equipment supplies materials
glass wood metal steel gold silver diamond jewelry watches fashion shoes bags
clothing style beauty hair skin makeup perfume pets dog cat vet veterinary
horse plumbing electrician roofing painting cleaning security protection
storage moving shipping delivery courier logistics freight transport
tienda mercado compras salud belleza moda hogar jardin abogado contador
seguros inmobiliaria propiedades construccion ingenieria educacion escuela
universidad noticias periodico radio tv cine teatro musica arte fotografia
deporte futbol restaurante comida turismo vuelos autos carros motos muebles
ropa zapatos joyas mascotas veterinaria farmacia clinica dentista medico
impuestos finanzas banco dinero inversion negocios empresa servicios
soluciones sistemas redes tecnologia software nube correo web sitio
ad ae af ag al am ao aq ar as at au aw ax az ba bb bd be bf bg bh bi bj bm
bn bo br bs bt bw by bz ca cc cd cf cg ch ci ck cl cm cn cr cu cv cw cx cy cz
de dj dk dm do dz ec ee eg er es et eu fi fj fk fm fo fr ga gb gd ge gf gg gh
gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht hu id ie il im in iq ir is
it je jm jo jp ke kg kh ki km kn kp kr kw ky kz la lb lc li lk lr ls lt lu lv
ly ma mc md me mg mh mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz na nc ne
nf ng ni nl no np nr nu nz om pa pe pf pg ph pk pl pm pn pr ps pt pw py qa re
ro rs ru rw sa sb sc sd se sg sh si sk sl sm sn so sr ss st su sv sx sy sz tc
td tf tg th tj tk tl tm tn to tr tt tv tw tz ua ug uk us uy uz va vc ve vg vi
vn vu wf ws ye yt za zm zw
""".split())

_LOCAL_CORREO_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+")
_ETIQUETA_DOMINIO_RE = re.compile(r"[a-z0-9-]+")
_EXTENSION_RE = re.compile(r"[a-z]{2,63}")


def _dominio_existe(dominio):
    """True/False si el DNS confirma o niega el dominio; None si no se pudo saber."""
    import socket
    import threading

    from django.conf import settings
    from django.core.cache import cache

    if not getattr(settings, "VALIDAR_DOMINIO_CORREO", True):
        return True

    clave = f"correo_dominio:{dominio}"
    cacheado = cache.get(clave)
    if cacheado is not None:
        return cacheado

    resultado = [None]

    def consultar():
        try:
            socket.getaddrinfo(dominio, 443, type=socket.SOCK_STREAM)
            resultado[0] = True
        except socket.gaierror as exc:
            no_existe = {
                getattr(socket, "EAI_NONAME", -2),
                getattr(socket, "EAI_NODATA", -5),
                11001,
                11004,
            }
            resultado[0] = False if exc.errno in no_existe else None
        except Exception:
            resultado[0] = None

    hilo = threading.Thread(target=consultar, daemon=True)
    hilo.start()
    hilo.join(3)

    if resultado[0] is None:
        return None
    cache.set(clave, resultado[0], 3600 if resultado[0] else 900)
    return resultado[0]


def validar_correo_electronico(correo):
    """Valida formato, dominio y extensión de un correo. Devuelve (válido, error)."""
    from django.conf import settings
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    correo = (correo or "").strip()
    if not correo:
        return False, "Escribe el correo electrónico."
    if correo.count("@") != 1:
        return False, "El correo debe contener un solo símbolo '@'."

    local, dominio = correo.split("@")
    if not local or not dominio:
        return False, "El correo está incompleto. Usa el formato usuario@dominio.com."
    if len(correo) > 254 or len(local) > 64:
        return False, "El correo es demasiado largo."
    if (
        not _LOCAL_CORREO_RE.fullmatch(local)
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
    ):
        return False, "La parte anterior al '@' no es válida."

    dominio = dominio.strip().lower().rstrip(".")
    if len(dominio) > 253 or ".." in dominio:
        return False, "El dominio del correo no es válido."

    etiquetas = dominio.split(".")
    if len(etiquetas) < 2:
        return False, (
            "El correo debe incluir un dominio y una extensión, "
            "por ejemplo: usuario@dominio.com."
        )
    for etiqueta in etiquetas:
        if (
            not etiqueta
            or len(etiqueta) > 63
            or etiqueta.startswith("-")
            or etiqueta.endswith("-")
            or not _ETIQUETA_DOMINIO_RE.fullmatch(etiqueta)
        ):
            return False, "El dominio del correo no es válido."

    extension = etiquetas[-1]
    if not _EXTENSION_RE.fullmatch(extension):
        return False, (
            "La extensión del correo no es válida. Usa una como .com o .co."
        )

    try:
        validate_email(correo)
    except ValidationError:
        return False, "El correo no es válido. Usa el formato usuario@dominio.com."

    verificar_dominio = getattr(settings, "VALIDAR_DOMINIO_CORREO", True)
    if extension not in _EXTENSIONES_CORREO and not verificar_dominio:
        return False, (
            "La extensión del correo no es válida. Usa una como .com o .co."
        )

    existe = _dominio_existe(dominio)
    if existe is False:
        return False, "El dominio del correo no existe. Revisa la dirección."
    if existe is None and extension not in _EXTENSIONES_CORREO:
        return False, (
            "No se pudo comprobar el dominio del correo. "
            "Usa una extensión como .com o .co."
        )

    return True, ""


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
                login_url = reverse("effiadmi:login")
                return redirect(f"{login_url}?next={request.get_full_path()}")

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
