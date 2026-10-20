"""Middlewares de seguridad del proyecto.

LoginThrottleMiddleware limita los POST a las vistas de acceso (login de la
app, login del admin y recuperacion de contrasena) por IP, para cortar la
fuerza bruta aunque el atacante cambie de usuario en cada intento. La vista
de login ademas aplica un candado por usuario (5 fallos = 15 min), de modo
que entre los dos cubren IP-rotando y usuario-rotando.
"""

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

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
