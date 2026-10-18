"""Vistas de nivel proyecto (no pertenecen a una app concreta)."""

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import Http404
from django.views.static import serve


def media_protegida(request, ruta):
    """Sirve archivos de /media/ (facturas, adjuntos) solo con sesion valida.

    En produccion `django.conf.urls.static.static()` no sirve nada con
    DEBUG=0; sin esta vista las facturas subidas darian 404, y si se
    sirvieran sin auth cualquiera con la URL se bajaria los PDFs.
    `serve()` resuelve la ruta con safe_join, asi que ../ no escapa de
    MEDIA_ROOT (SuspiciousFileOperation -> 404).
    """
    logueado = request.session.get("logueado") or request.user.is_authenticated
    if not logueado:
        raise Http404
    try:
        return serve(request, ruta, document_root=settings.MEDIA_ROOT)
    except SuspiciousFileOperation:
        raise Http404
