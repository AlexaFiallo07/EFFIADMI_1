"""Middlewares de seguridad del proyecto.

LoginThrottleMiddleware limita los POST a las vistas de acceso (login de la
app, login del admin y recuperacion de contrasena) por IP, para cortar la
fuerza bruta aunque el atacante cambie de usuario en cada intento. La vista
de login ademas aplica un candado por usuario (5 fallos = 15 min), de modo
que entre los dos cubren IP-rotando y usuario-rotando.
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseNotFound

from base.seguridad import ip_en_redes

logger = logging.getLogger("django.security")

# Rutas que reciben POST de credenciales (subcadenas del path).
RUTAS_CREDENCIALES = ("/login", "/recuperar-password", "/restablecer-password")

# (limite de POST, ventana en segundos) por IP y ruta.
LIMITES = {
    "login": (10, 60),
    "recuperar": (3, 600),
}


def ip_real_del_request(request):
    """IP del cliente sin dar por buena una cabecera X-Forwarded-For falsificada.

    Por defecto se ignora el XFF (cualquier cliente puede mandarlo) y se usa
    REMOTE_ADDR. Solo con TRUST_X_FORWARDED_FOR=1 (hay un proxy de confianza
    delante que SOBRESCRIBE la cabecera) se toma la ULTIMA IP de la lista, que
    es la que vio el proxy. Antes se leia la primera entrada, con lo que un
    atacante rotando XFF evadia el limite de login/recuperacion.
    """
    if getattr(settings, "TRUST_PROXY_XFF", False):
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            candidata = xff.split(",")[-1].strip()
            if candidata:
                return candidata[:45]
    return (request.META.get("REMOTE_ADDR", "") or "desconocida")[:45]


def _clave(path):
    if "recuperar-password" in path or "restablecer-password" in path:
        return "recuperar"
    return "login"


class LoginThrottleMiddleware:
    """Devuelve 429 si una IP supera el limite de POST a rutas de credenciales."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and any(
            ruta in request.path for ruta in RUTAS_CREDENCIALES
        ):
            tipo = _clave(request.path)
            maximo, ventana = LIMITES[tipo]
            ip = ip_real_del_request(request)
            clave = f"throttle:{tipo}:{ip}"
            try:
                intentos = cache.incr(clave)
            except ValueError:
                cache.set(clave, 1, ventana)
                intentos = 1
            if intentos > maximo:
                return HttpResponse(
                    "Demasiados intentos. Espera un minuto y vuelve a intentarlo.",
                    status=429,
                    content_type="text/plain; charset=utf-8",
                )
        return self.get_response(request)


class CabecerasSeguridadMiddleware:
    """Anade Content-Security-Policy y Permissions-Policy.

    Django no las pone por defecto. Sin CSP, un XSS (o un CDN comprometido)
    ejecuta cualquier script en el origen de la app. La politica permite los
    dos CDN que ya usa el front (jsdelivr para Chart.js y Google Fonts) y
    'unsafe-inline' porque las plantillas usan estilos y scripts inline; aun
    asi bloquea cualquier origen no listado.
    """

    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )

    PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=()"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", self.CSP)
        response.headers.setdefault("Permissions-Policy", self.PERMISSIONS_POLICY)
        return response


class AdminAccessMiddleware:
    """Oculta /admin/ a las IP que no esten en ADMIN_ALLOWED_IPS."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        redes = getattr(settings, "ADMIN_ALLOWED_NETWORKS", ())
        ruta_admin = f"/{getattr(settings, 'ADMIN_URL', 'admin/').rstrip('/')}"
        path = request.path_info
        if redes and (path == ruta_admin or path.startswith(f"{ruta_admin}/")):
            ip = ip_real_del_request(request)
            if not ip_en_redes(ip, redes):
                logger.warning("Acceso a admin bloqueado para IP %s en %s", ip, path)
                return HttpResponseNotFound("No encontrado.")
        return self.get_response(request)
