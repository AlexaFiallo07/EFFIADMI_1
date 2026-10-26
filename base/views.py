"""Vistas de nivel proyecto (no pertenecen a una app concreta)."""

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404
from django.utils._os import safe_join


def _usuario_autenticado(request):
    """Usuario real de la peticion (sesion Django o la sesion propia 'logueado')."""
    from django.contrib.auth import get_user_model

    if request.user.is_authenticated:
        return request.user
    datos = request.session.get("logueado") or {}
    if not datos.get("id"):
        return None
    return (
        get_user_model()
        .objects.filter(pk=datos["id"], is_active=True)
        .first()
    )


def media_protegida(request, ruta):
    """Sirve un adjunto de /media/ solo a quien tiene derecho a verlo.

    Antes bastaba con tener sesion: cualquier operador autenticado podia
    descargar la factura de compra de otro cambiando la URL (IDOR). Ahora se
    resuelve el archivo contra FacturaCompra y solo lo ve el admin o quien lo
    subio. Un archivo que no pertenece a ninguna FacturaCompra da 404.

    `safe_join` resuelve la ruta con proteccion contra ../, asi que no se
    puede escapar de MEDIA_ROOT (SuspiciousFileOperation -> 404).
    """
    from effiadmi.models import FacturaCompra, UserProfile

    usuario = _usuario_autenticado(request)
    if usuario is None:
        raise Http404

    factura = FacturaCompra.objects.filter(archivo=ruta).only("usuario_id").first()
    if factura is None:
        raise Http404

    rol = (
        UserProfile.objects.filter(user=usuario)
        .values_list("cargo", flat=True)
        .first()
        or ""
    )
    es_admin = rol == "admin" or usuario.is_superuser
    if not (es_admin or factura.usuario_id == usuario.id):
        raise Http404

    try:
        destino = safe_join(settings.MEDIA_ROOT, ruta)
        return FileResponse(open(destino, "rb"))
    except (SuspiciousFileOperation, FileNotFoundError, IsADirectoryError, OSError):
        raise Http404
