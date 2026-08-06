from django.urls import path
from . import views

app_name = 'effiadmi'
urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/lista/', views.lista_clientes, name='lista_clientes'),
    path('clientes/crear/', views.crear_cliente, name='crear_cliente'),
    path('clientes/editar/<int:id>/', views.formulario_clientes, name='editar_cliente'),
    path('inventario/', views.inventario, name='inventario'),
    path('notificaciones/', views.notificaciones, name='notificaciones'),
    path('pagos/', views.pagos, name='pagos'),
    path('pedidos/', views.pedidos, name='pedidos'),
    path('productos/', views.productos, name='productos'),
    path('proveedores/', views.proveedores, name='proveedores'),
    path('facturas/', views.facturas, name='facturas'),
    path('reportes/', views.reportes, name='reportes'),
    path('usuarios/', views.usuarios, name='usuarios'),
    path('perfil/', views.perfil, name='perfil'),
    path('productos/crear/', views.crear_producto, name='crear_producto'),
    path('facturas/crear/', views.crear_factura, name='crear_factura'),
    path('pedidos/crear/', views.crear_pedido, name='crear_pedido'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
]
