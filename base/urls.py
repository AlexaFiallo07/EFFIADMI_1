"""
URL configuration for base project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path
from base.views import media_protegida

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('effiadmi.api_urls')),
    # /media/ solo con sesion (facturas, adjuntos): en produccion DEBUG=0
    # no sirve nada, y sin auth cualquiera con la URL se bajaria los PDFs.
    re_path(r'^media/(?P<ruta>.*)$', media_protegida, name='media_protegida'),
    path('', include('landing.urls')),
    path('app/', include('effiadmi.urls')),
]

# Desarrollo y produccion: /static/ lo sirve whitenoise (DEBUG=0) o el
# runserver (DEBUG=1); /media/ siempre pasa por media_protegida.