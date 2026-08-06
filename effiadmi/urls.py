from django.urls import path
from . import views

app_name = 'effiadmi'
urlpatterns = [
    # ==================== AUTH ====================
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    
    # ==================== DASHBOARD ====================
    path('', views.inicio, name='inicio'),
    path('perfil/', views.perfil, name='perfil'),
    
    # ==================== CLIENTES ====================
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/crear/', views.crear_cliente, name='crear_cliente'),
    path('clientes/<int:id>/editar/', views.editar_cliente, name='editar_cliente'),
    path('clientes/<int:id>/eliminar/', views.eliminar_cliente, name='eliminar_cliente'),
    
    # ==================== INVENTARIO ====================
    path('inventario/', views.lista_inventario, name='lista_inventario'),
    path('inventario/crear/', views.crear_inventario, name='crear_inventario'),
    path('inventario/<int:id>/editar/', views.editar_inventario, name='editar_inventario'),
    path('inventario/<int:id>/eliminar/', views.eliminar_inventario, name='eliminar_inventario'),
    
    # ==================== PRODUCTOS ====================
    path('productos/', views.lista_productos, name='lista_productos'),
    path('productos/crear/', views.crear_producto, name='crear_producto'),
    path('productos/<int:id>/editar/', views.editar_producto, name='editar_producto'),
    path('productos/<int:id>/eliminar/', views.eliminar_producto, name='eliminar_producto'),
    
    # ==================== FACTURAS ====================
    path('facturas/', views.lista_facturas, name='lista_facturas'),
    path('facturas/crear/', views.crear_factura, name='crear_factura'),
    path('facturas/<int:id>/', views.detalle_factura, name='detalle_factura'),
    path('facturas/<int:id>/editar/', views.editar_factura, name='editar_factura'),
    path('facturas/<int:id>/eliminar/', views.eliminar_factura, name='eliminar_factura'),
    
    # ==================== PEDIDOS ====================
    path('pedidos/', views.lista_pedidos, name='lista_pedidos'),
    path('pedidos/crear/', views.crear_pedido, name='crear_pedido'),
    path('pedidos/<int:id>/', views.detalle_pedido, name='detalle_pedido'),
    path('pedidos/<int:id>/editar/', views.editar_pedido, name='editar_pedido'),
    path('pedidos/<int:id>/eliminar/', views.eliminar_pedido, name='eliminar_pedido'),
    
    # ==================== USUARIOS ====================
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('usuarios/<int:id>/editar/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/<int:id>/eliminar/', views.eliminar_usuario, name='eliminar_usuario'),
    
    # ==================== PROVEEDORES ====================
    path('proveedores/', views.lista_proveedores, name='lista_proveedores'),
    path('proveedores/crear/', views.crear_proveedor, name='crear_proveedor'),
    path('proveedores/<int:id>/editar/', views.editar_proveedor, name='editar_proveedor'),
    path('proveedores/<int:id>/eliminar/', views.eliminar_proveedor, name='eliminar_proveedor'),
    
    # ==================== NOTIFICACIONES ====================
    path('notificaciones/', views.lista_notificaciones, name='lista_notificaciones'),
    path('notificaciones/<int:id>/', views.detalle_notificacion, name='detalle_notificacion'),
    path('notificaciones/<int:id>/eliminar/', views.eliminar_notificacion, name='eliminar_notificacion'),
    
    # ==================== REPORTES ====================
    path('reportes/', views.reportes_view, name='reportes'),
]
