from django.urls import path
from landing import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('solucion/', views.solucion, name='solucion'),
    path('modulos/', views.modulos, name='modulos'),
    path('modulos/<str:slug>/', views.modulo, name='modulo'),
    path('como-funciona/', views.proceso, name='proceso'),
    path('tecnologia/', views.tecnologia, name='tecnologia'),
    path('contacto/', views.contacto, name='contacto'),
]